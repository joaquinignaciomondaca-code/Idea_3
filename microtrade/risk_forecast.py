"""Segundo momento diario: hipótesis de riesgo, no dirección ni PnL."""
import math
from datetime import date,datetime,time,timedelta,timezone
import numpy as np
from .online import canonical

MODELS=('constant_train','rolling20','rolling60','ewma94','range20')


def series(rows):
    dates=[r.date for r in rows]
    if len(set(dates))!=len(dates) or any((date.fromisoformat(b)-date.fromisoformat(a)).days!=1 for a,b in zip(dates,dates[1:])):
        raise ValueError('Se requieren días UTC consecutivos.')
    c=np.array([r.close for r in rows]);h=np.array([r.high for r in rows]);l=np.array([r.low for r in rows])
    if not np.isfinite([c,h,l]).all() or (l<=0).any() or (h<l).any() or (c<l).any() or (c>h).any():raise ValueError('OHLC inválido.')
    r2=np.full(len(c),np.nan);r2[1:]=np.log(c[1:]/c[:-1])**2
    ranges=np.log(h/l)**2/(4*math.log(2))
    return r2,ranges


def forecasts(rows,cutoff,constant):
    if not math.isfinite(constant) or constant<=0 or not 60<=cutoff<len(rows):raise ValueError('Baseline/cutoff inválido.')
    r2,ranges=series(rows[:cutoff+1])
    if cutoff<60:raise ValueError('Warmup insuficiente.')
    v=float(np.mean(r2[1:61]))
    for j in range(61,cutoff+1):v=.94*v+.06*float(r2[j])
    result={'constant_train':constant,'rolling20':float(np.mean(r2[cutoff-19:cutoff+1])),
            'rolling60':float(np.mean(r2[cutoff-59:cutoff+1])),'ewma94':v,'range20':float(np.mean(ranges[cutoff-19:cutoff+1]))}
    return {k:max(1e-12,float(v)) for k,v in result.items()}


def loss(h,y):
    if not math.isfinite(h) or not math.isfinite(y) or h<=0 or y<0:raise ValueError('Varianza/proxy inválida.')
    return math.log(h)+y/h


def study(rows,spec):
    if spec['models']!=list(MODELS) or spec['hpo_trials']!=0:raise ValueError('Protocolo distinto.')
    r2,_=series(rows);idx={r.date:i for i,r in enumerate(rows)};start=idx[spec['test'][0]];end=idx[spec['test'][1]]
    # Constant benchmark fitted ONCE before first forecast. Same value in future protocol.
    train_end=start-2;constant=float(np.mean(r2[1:train_end+1]));records=[]
    for target in range(start,end+1):
        pred=forecasts(rows,target-2,constant)
        records.append({'target':rows[target].date,'cutoff':rows[target-2].date,'y':float(r2[target]),'forecasts':pred})
    def score(rr):
        return {m:{'n':len(rr),'qlike':float(np.mean([loss(r['forecasts'][m],r['y']) for r in rr])),
                   'mse':float(np.mean([(r['forecasts'][m]-r['y'])**2 for r in rr])),
                   'mean_forecast':float(np.mean([r['forecasts'][m] for r in rr])),'mean_proxy':float(np.mean([r['y'] for r in rr]))} for m in MODELS}
    blocks=[]
    for a,b in spec['blocks']:
        rr=[r for r in records if a<=r['target']<=b];blocks.append({'test':[a,b],'metrics':score(rr)})
    ci={}
    for m in ('ewma94','rolling60','range20'):
        ci[m]={}
        for length in (14,60):
            rng=np.random.default_rng(1701);sums=np.zeros(2000)
            for a,b in spec['blocks']:
                rr=[r for r in records if a<=r['target']<=b];d=np.array([loss(r['forecasts'][m],r['y'])-loss(r['forecasts']['rolling20'],r['y']) for r in rr]);n=len(d)
                starts=rng.integers(0,n,size=(2000,(n+length-1)//length));ix=((starts[:,:,None]+np.arange(length))%n).reshape(2000,-1)[:,:n]
                sums+=d[ix].sum(axis=1)
            lo,hi=np.percentile(sums/len(records),[2.5,97.5]);sc=score(records)
            ci[m][str(length)]={'delta_qlike':sc[m]['qlike']-sc['rolling20']['qlike'],'lower95':float(lo),'upper95':float(hi)}
    return {'metrics':score(records),'blocks':blocks,'paired_ci_vs_rolling20':ci,'constant_train':constant,
            'constant_training_end':rows[train_end].date,'records':records,'winner_promoted':False}


def prospective_record(rows,now,spec,path,constant):
    """Guard local. Validez prospectiva requiere además timestamp de publicación externo."""
    if now.tzinfo is None:raise ValueError('Timestamp sin zona.')
    now=now.astimezone(timezone.utc);cutoff=date.fromisoformat(rows[-1].date);target=cutoff+timedelta(days=2)
    if cutoff!=now.date()-timedelta(days=1) or not spec['start']<=target.isoformat()<=spec['end']:
        raise ValueError('Datos atrasados/futuros o target fuera de reserva.')
    if not datetime.combine(target-timedelta(days=1),time(),timezone.utc)<=now<datetime.combine(target,time(),timezone.utc):raise ValueError('Fuera del plazo de emisión.')
    record={'experiment_id':spec['id'],'target':target.isoformat(),'cutoff':cutoff.isoformat(),'created_at_utc':now.isoformat(),
            'forecasts':forecasts(rows,len(rows)-1,constant),'target_observed':False,
            'external_publication_required':True,'trading_backtest':False}
    with path.open('x') as f:f.write(canonical(record)+'\n')
    return record
