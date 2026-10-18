"""Adaptación parcial de momentum semanal: OLS y ridge cerrada, sin SGD/HPO."""
from datetime import date
import numpy as np
from .feature_study import fit_scaler,transform


def examples(rows):
    c=np.array([r.close for r in rows]);returns=np.zeros(len(rows));returns[1:]=np.log(c[1:]/c[:-1])
    result=[]
    for i in range(84,len(rows)-8):
        if date.fromisoformat(rows[i].date).weekday()!=6:continue
        result.append({'index':i,'signal':rows[i].date,'entry':rows[i+2].date,'end':rows[i+8].date,
                       'x':[float(np.log(c[i]/c[i-k])) for k in (7,28,84)]+[float(np.std(returns[i-27:i+1]))],
                       'y':rows[i+8].close/rows[i+2].open-1})
    return result


def metrics(records):
    y=np.array([r['y'] for r in records]);p=np.array([r['prediction'] for r in records]);b=np.array([r['historical_mean'] for r in records])
    mse=float(np.mean((p-y)**2));base=float(np.mean((b-y)**2))
    return {'n':len(records),'mse':mse,'mae':float(np.mean(abs(p-y))),
            'r2_oos_vs_historical_mean':1-mse/base if base>0 else None,
            'direction_accuracy':float(np.mean((p>0)==(y>0)))}


def run(rows,spec):
    if spec['id']!='WEEKLY-RETURN-ADAPTATION-001' or spec['ridge_alpha']!=1 or spec['outer_years']!=[2024,2025,2026]:
        raise ValueError('Configuración fuera del preregistro.')
    samples=examples(rows);pooled={k:[] for k in ('zero','historical_mean','ols_momentum7','ridge4')}
    blocks=[];fits=[]
    for year in spec['outer_years']:
        test=[r for r in samples if int(r['signal'][:4])==year]
        if not test:raise ValueError('Bloque vacío.')
        cutoff=test[0]['signal'];train=[r for r in samples if r['end']<=cutoff and r['signal']<cutoff]
        if len(train)<spec['minimum_training_weeks']:raise ValueError('Train semanal insuficiente.')
        x=np.array([r['x'] for r in train]);y=np.array([r['y'] for r in train]);mean=float(np.mean(y))
        center,scale=fit_scaler(x);xx=transform(x,center,scale)
        # Misma escala para OLS y ridge; OLS usa solo intercepto y momentum7.
        w_ols=np.linalg.lstsq(xx[:,:2],y,rcond=None)[0]
        penalty=np.diag([0.,1.,1.,1.,1.]);a=xx.T@xx/len(y)+spec['ridge_alpha']*penalty
        w_ridge=np.linalg.solve(a,xx.T@y/len(y))
        residual=float(np.max(abs(a@w_ridge-xx.T@y/len(y))))
        if residual>1e-10:raise ValueError('Ridge no resuelve ecuaciones normales.')
        fit={'year':year,'cutoff':cutoff,'training_weeks':len(train),'last_training_target':train[-1]['end'],
             'center':center.tolist(),'scale':scale.tolist(),'ols_weights':w_ols.tolist(),'ridge_weights':w_ridge.tolist(),'ridge_normal_equation_error':residual}
        fits.append(fit);by_model={k:[] for k in pooled}
        for r in test:
            xx_test=transform(np.array([r['x']]),center,scale)[0]
            preds={'zero':0.,'historical_mean':mean,'ols_momentum7':float(xx_test[:2]@w_ols),'ridge4':float(xx_test@w_ridge)}
            for name,p in preds.items():
                record={k:r[k] for k in ('signal','entry','end','y')};record.update({'prediction':p,'historical_mean':mean})
                by_model[name].append(record);pooled[name].append(record)
        blocks.append({'year':year,'first_signal':test[0]['signal'],'last_signal':test[-1]['signal'],
                       'metrics':{k:metrics(v) for k,v in by_model.items()}})
    intervals={}
    for name in ('zero','ols_momentum7','ridge4'):
        intervals[name]={}
        for length in (4,12):
            rng=np.random.default_rng(1701); simulated=np.zeros(2000); total=0
            for year in spec['outer_years']:
                rr=[r for r in pooled[name] if int(r['signal'][:4])==year]
                d=np.array([(r['prediction']-r['y'])**2-(r['historical_mean']-r['y'])**2 for r in rr]);n=len(d)
                starts=rng.integers(0,n,size=(2000,(n+length-1)//length))
                indices=((starts[:,:,None]+np.arange(length))%n).reshape(2000,-1)[:,:n]
                simulated+=d[indices].sum(axis=1);total+=n
            lo,hi=np.percentile(simulated/total,[2.5,97.5])
            intervals[name][str(length)]={'mean_loss_difference':metrics(pooled[name])['mse']-metrics(pooled['historical_mean'])['mse'],
                                         'lower_95':float(lo),'upper_95':float(hi)}
    return {'blocks':blocks,'fits':fits,'pooled':{k:metrics(v) for k,v in pooled.items()},'predictions':pooled,'paired_loss_ci':intervals,
            'model_fits_per_pass':6,'winner_promoted':False,'trading_backtest':False,'historically_pristine_holdout':False}
