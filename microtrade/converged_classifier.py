"""Comparación controlada: SGD10 vs objetivo batch convergido. Solo retrospectivo."""
import numpy as np
from scipy.optimize import minimize
from .feature_study import NAMES,BASELINE,prepare,fit_scaler,transform,step
from .numerical_audit import derivatives,scipy_objective,objective
from .online import aggregate


def solve(x,y,alpha):
    w=np.zeros(x.shape[1])
    for iteration in range(100):
        g,h=derivatives(w,x,y,alpha)
        if np.max(abs(g))<1e-8:return w,iteration
        direction=np.linalg.solve(h,g);old=objective(w,x,y,alpha);rate=1.
        for _ in range(60):
            candidate=w-rate*direction
            # Rounding allowance only at machine precision; gradient still gates exit.
            if objective(candidate,x,y,alpha)<=old-1e-4*rate*float(g@direction)+4*np.finfo(float).eps*max(1.,abs(old)):
                w=candidate;break
            rate*=.5
        else:raise ValueError('Line search no converge.')
    raise ValueError('Solver no converge.')


def fit_predict(data,start,end,names,alpha,spec,sgd=False,verify=False):
    cutoff=start-2;eligible=np.arange(90,cutoff-1)[-365:]
    if len(eligible)<60:raise ValueError('Train insuficiente.')
    raw=data['x'][:,[NAMES.index(n) for n in names]];center,scale=fit_scaler(raw[eligible])
    x=transform(raw,center,scale);xx=x[eligible];y=data['y'][eligible+2]
    if set(y)!={0,1}:raise ValueError('Faltan clases.')
    if sgd:
        w=np.zeros(len(names)+1)
        for _ in range(10):
            for row,label in zip(xx,y):w=step(w,row,int(label),{'learning_rate':.001,'l2':alpha})
        iterations=10
    else:w,iterations=solve(xx,y,alpha)
    grad=float(np.max(abs(derivatives(w,xx,y,alpha)[0])))
    z=xx@w
    if np.max(abs(z))>=35 or (not sgd and grad>1e-7):raise ValueError('No converge o clipping activo.')
    agreement=None
    if verify:
        ref=minimize(scipy_objective,np.zeros(len(w)),args=(xx,y,alpha),method='L-BFGS-B',jac='3-point',options={'ftol':1e-15,'gtol':1e-9,'maxiter':2000,'maxls':50})
        agreement=float(np.max(abs(ref.x-w)))
        if not ref.success or agreement>1e-4 or abs(objective(ref.x,xx,y,alpha)-objective(w,xx,y,alpha))>1e-9:raise ValueError('SciPy discrepa.')
    records=[]
    for target in range(start,end+1):
        p=float(np.exp(-np.logaddexp(0,-float(x[target-2]@w))))
        records.append({'target':data['dates'][target],'p':p,'y':int(data['y'][target]),'persistence':.55 if data['y'][target-2] else .45})
    return {'records':records,'metrics':aggregate([(r['p'],r['y']) for r in records]),
            'fit':{'cutoff':data['dates'][cutoff],'last_training_label':data['dates'][int(eligible[-1])+2],
                   'training_rows':len(eligible),'alpha':alpha,'gradient_inf':grad,'iterations':iterations,
                   'scipy_weight_max_difference':agreement,'center':center.tolist(),'scale':scale.tolist(),'weights':w.tolist(),
                   'historical_prior':float((sum(y)+1)/(len(y)+2))}}


def study(rows,spec):
    if spec['alphas']!=[.001,.01,.1] or spec['search_candidates']!=18:raise ValueError('Presupuesto diferente.')
    data=prepare(rows);idx={d:i for i,d in enumerate(data['dates'])};blocks=[];selections=[];fits=[];pooled={};predictions={};fit_count=0
    for block in spec['outer_blocks']:
        start,end=[idx[d] for d in block['test']];cutoff=start-2
        if max(b for _,b in block['inner'])>data['dates'][cutoff]:raise ValueError('Selección invade test.')
        past=prepare(rows[:cutoff+1]);pi={d:i for i,d in enumerate(past['dates'])};chosen={}
        for label,names in (('baseline3',BASELINE),('all24',NAMES)):
            trials=[]
            for alpha in spec['alphas']:
                rr=[fit_predict(past,pi[a],pi[b],names,alpha,spec) for a,b in block['inner']];fit_count+=2
                n=[r['metrics']['n'] for r in rr];losses=[r['metrics']['log_loss'] for r in rr]
                trials.append({'alpha':alpha,'fold_n':n,'fold_losses':losses,'value':sum(k*v for k,v in zip(n,losses))/sum(n)})
            best=min(trials,key=lambda t:(t['value'],t['alpha']));chosen[label]=best['alpha']
            selections.append({'block':block['name'],'features':label,'selection_data_end':past['dates'][-1],'alpha':best['alpha'],'trials':trials})
        metrics={};control=None
        for label,names in (('baseline3',BASELINE),('all24',NAMES)):
            for mode,alpha,sgd in (('sgd10',.01,True),('converged_same_alpha',.01,False),('converged_selected',chosen[label],False)):
                name=label+'/'+mode;r=fit_predict(data,start,end,names,alpha,spec,sgd=sgd,verify=not sgd);fit_count+=1
                metrics[name]=r['metrics'];fits.append({'block':block['name'],'model':name,**r['fit']})
                pairs=[(p['p'],p['y']) for p in r['records']];pooled.setdefault(name,[]).extend(pairs)
                predictions.setdefault(name,[]).extend(r['records'])
                if control is None:control=r
        for name,values in (('constant_p0_5',[(.5,r['y']) for r in control['records']]),('historical_prior',[(control['fit']['historical_prior'],r['y']) for r in control['records']]),('persistence',[(r['persistence'],r['y']) for r in control['records']])):
            metrics[name]=aggregate(values);pooled.setdefault(name,[]).extend(values)
        blocks.append({'name':block['name'],'test':block['test'],'metrics':metrics})
    if fit_count!=54 or len(selections)!=6:raise ValueError('Fits/candidatos incompletos.')
    # Intervalos descriptivos emparejados, sin seleccionar modelo por el intervalo.
    ci={}
    for label in ('baseline3','all24'):
        name=label+'/converged_selected';ci[name]={}
        for reference in ('constant_p0_5','historical_prior',label+'/sgd10'):
            from .online import scores
            d=np.array([scores(p,y)['log_loss']-scores(q,z)['log_loss'] for (p,y),(q,z) in zip(pooled[name],pooled[reference])])
            ci[name][reference]={}
            for length in (14,60):
                rng=np.random.default_rng(1701);summed=np.zeros(2000);offset=0
                for b in blocks:
                    n=b['metrics'][name]['n'];part=d[offset:offset+n];offset+=n
                    starts=rng.integers(0,n,size=(2000,(n+length-1)//length))
                    indices=((starts[:,:,None]+np.arange(length))%n).reshape(2000,-1)[:,:n]
                    summed+=part[indices].sum(axis=1)
                low,high=np.percentile(summed/len(d),[2.5,97.5])
                ci[name][reference][str(length)]={'mean_difference':float(np.mean(d)),'lower_95':float(low),'upper_95':float(high)}
    return {'blocks':blocks,'selections':selections,'fit_audit':fits,'fits_per_pass':fit_count,
            'search_candidates':18,'pooled':{k:aggregate(v) for k,v in pooled.items()},'paired_loss_ci':ci,
            'predictions':predictions,'winner_promoted':False,'trading_backtest':False,'historically_pristine_holdout':False}
