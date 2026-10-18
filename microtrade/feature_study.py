"""24 señales causales y ablaciones con reentrenamiento. Solo diagnóstico predictivo."""
import math
from dataclasses import dataclass
import numpy as np
from .online import aggregate, canonical, state_hash

FAMILIES = {
    'trend': ['return_1','return_5','return_10','return_20','return_60','return_90'],
    'volatility': ['vol_5','vol_20','vol_60','range_log','atr_20','downside_20'],
    'activity': ['volume_relative_20','quote_relative_20','trades_relative_20','trade_size_relative_20','taker_imbalance','illiquidity_proxy'],
    'candles': ['intraday_return','upper_wick','lower_wick','open_gap','up_fraction_20','close_position_20']}
NAMES = sum(FAMILIES.values(), [])
BASELINE = ['return_1','return_5','vol_20']


@dataclass(frozen=True)
class Candle:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    taker_quote: float


def prepare(rows):
    if len({r.date for r in rows}) != len(rows) or [r.date for r in rows] != sorted(r.date for r in rows):
        raise ValueError('Fechas duplicadas/desordenadas.')
    a = np.array([[r.open,r.high,r.low,r.close,r.volume,r.quote_volume,r.trades,r.taker_quote] for r in rows],dtype=float)
    if not np.isfinite(a).all() or (a[:,:7] <= 0).any() or (a[:,7] < 0).any() or (a[:,7] > a[:,5]*(1+1e-10)).any():
        raise ValueError('OHLCV/actividad no finitos, no positivos o inconsistente.')
    o,h,l,c,v,q,t,buy = a.T
    if ((l>np.minimum(o,c)) | (h<np.maximum(o,c)) | (h<l)).any():
        raise ValueError('OHLC inconsistente.')
    returns = np.zeros(len(rows)); returns[1:] = np.log(c[1:]/c[:-1])
    true_range = np.maximum(h-l, np.maximum(np.abs(h-np.r_[c[0],c[:-1]]),np.abs(l-np.r_[c[0],c[:-1]])))
    x = np.full((len(rows),24),np.nan)
    for i in range(90,len(rows)):
        sl = slice(i-19,i+1); width = h[i]-l[i]; span = max(h[sl])-min(l[sl])
        trend = [math.log(c[i]/c[i-k]) for k in (1,5,10,20,60,90)]
        volatility = [float(np.std(returns[i-k+1:i+1])) for k in (5,20,60)] + [math.log(h[i]/l[i]),float(np.mean(true_range[sl])/c[i]),float(np.sqrt(np.mean(np.minimum(returns[sl],0)**2)))]
        activity = [math.log(v[i]/np.mean(v[sl])),math.log(q[i]/np.mean(q[sl])),math.log(t[i]/np.mean(t[sl])),
                    math.log((q[i]/t[i])/np.mean(q[sl]/t[sl])),2*buy[i]/q[i]-1,abs(returns[i])/(q[i]/1e6)]
        candles = [math.log(c[i]/o[i]),(h[i]-max(o[i],c[i]))/width if width else 0,
                   (min(o[i],c[i])-l[i])/width if width else 0, math.log(o[i]/c[i-1]),
                   float(np.mean(c[sl]>o[sl])),(c[i]-min(l[sl]))/span if span else .5]
        x[i] = trend+volatility+activity+candles
    if not np.isfinite(x[90:]).all():
        raise ValueError('Feature no finita.')
    return {'dates':[r.date for r in rows], 'x':x, 'y':(c>o).astype(int)}


def fit_scaler(x):
    center = np.median(x,axis=0); q1,q3 = np.percentile(x,[25,75],axis=0)
    scale = q3-q1; scale = np.where(scale>0,scale,1.)
    return center,scale


def transform(x,center,scale):
    z = np.clip((x-center)/scale,-5,5)
    return np.column_stack((np.ones(len(z)),z))


def prob(w,x):
    z = max(-35.,min(35.,float(w@x)))
    return 1/(1+math.exp(-z))


def step(w,x,y,spec):
    penalty = w.copy(); penalty[0] = 0
    return w-spec['learning_rate']*((prob(w,x)-y)*x+spec['l2']*penalty)


def run_block(data,start,end,names,adaptive,spec):
    cutoff = start-2
    if cutoff<92 or end>=len(data['dates']) or start>end:
        raise ValueError('Bloque inválido o sin warmup.')
    eligible = np.arange(90,cutoff-1)[-spec['training_window']:]
    if len(eligible)<spec['minimum_training_rows']:
        raise ValueError('Entrenamiento insuficiente.')
    cols = [NAMES.index(n) for n in names]
    raw = data['x'][:,cols]; center,scale = fit_scaler(raw[eligible])
    # Cada fila se transforma con estadísticas del train de ESTE fit, nunca del test.
    x = transform(raw,center,scale); y = data['y']; w = np.zeros(len(names)+1)
    for _ in range(spec['epochs']):
        for j in eligible:
            w = step(w,x[j],int(y[j+2]),spec)
    fit = {'cutoff':data['dates'][cutoff], 'last_training_feature':data['dates'][int(eligible[-1])],
           'last_training_label':data['dates'][int(eligible[-1])+2], 'training_rows':len(eligible),
           'features':list(names), 'center':center.tolist(), 'scale':scale.tolist(), 'weights':w.tolist()}
    pending = {}; records = []
    for i in range(cutoff,end+1):
        if i in pending:
            r = pending.pop(i); r['y'] = int(y[i]); records.append(r)
            if adaptive:
                w = step(w,x[r['cutoff_index']],int(y[i]),spec)
        if start<=i+2<=end:
            pending[i+2] = {'cutoff_index':i, 'target':data['dates'][i+2], 'p':prob(w,x[i]),
                            'snapshot':state_hash(w.tolist())}
    if pending or len(records)!=end-start+1:
        raise ValueError('Cobertura incompleta.')
    return {'metrics':aggregate([(r['p'],r['y']) for r in records]), 'fit':fit, 'records':records}


def weighted_loss(runs):
    return sum(r['metrics']['n']*r['metrics']['log_loss'] for r in runs)/sum(r['metrics']['n'] for r in runs)


def study(rows,spec):
    if spec['features'] != FAMILIES or spec['max_fits_per_pass'] != 390 or len(spec['outer_blocks']) != 3:
        raise ValueError('Esquema/presupuesto diferente del preregistro.')
    data = prepare(rows); index = {d:i for i,d in enumerate(data['dates'])}
    blocks = []; selections = []; traces = []; fits = []; fit_count = 0
    outer_names = ['all24','baseline3','selected_inner']+['without_'+g for g in FAMILIES]
    pooled = {mode+'/'+name:[] for mode in ('fixed','adaptive') for name in outer_names}
    pooled.update({'constant_p0_5':[], 'persistence':[]})
    for block in spec['outer_blocks']:
        start,end = [index[d] for d in block['test']]; cutoff = start-2
        if max(e for _,e in block['inner'])>data['dates'][cutoff] or (blocks and block['test'][0]<=blocks[-1]['test'][1]):
            raise ValueError('Validación invade test o bloques solapados.')
        # No se pasa el dataset completo al análisis de importancia/selección.
        past = prepare(rows[:cutoff+1]); past_index = {d:i for i,d in enumerate(past['dates'])}
        inner = [(past_index[a],past_index[b]) for a,b in block['inner']]
        choices = {}
        for mode in ('fixed','adaptive'):
            adaptive = mode=='adaptive'
            full = [run_block(past,a,b,NAMES,adaptive,spec) for a,b in inner]; fit_count+=2
            rankings = []; group_importance = []
            for kind,units in (('feature',{n:[n] for n in NAMES}),('family',FAMILIES)):
                for name,removed in units.items():
                    kept = [n for n in NAMES if n not in removed]
                    dropped = [run_block(past,a,b,kept,adaptive,spec) for a,b in inner]; fit_count+=2
                    delta = [d['metrics']['log_loss']-f['metrics']['log_loss'] for d,f in zip(dropped,full)]
                    item = {'name':name, 'delta_log_loss':weighted_loss(dropped)-weighted_loss(full),
                            'delta_by_fold':delta, 'positive_both_folds':all(v>0 for v in delta)}
                    (rankings if kind=='feature' else group_importance).append(item)
            rankings.sort(key=lambda r:(-r['delta_log_loss'],r['name']))
            selected = [r['name'] for r in rankings if r['positive_both_folds']][:spec['max_selected_features']]
            choices[mode] = selected
            selections.append({'block':block['name'],'mode':mode,'selection_data_end':past['dates'][-1],
                               'selected_features':selected, 'inner_full_log_loss':weighted_loss(full),
                               'inner_fold_n':[r['metrics']['n'] for r in full], 'feature_importance':rankings,
                               'family_importance':group_importance})
        metrics = {}; base_records = None
        # Ambas selecciones congeladas antes de medir este bloque externo.
        for mode in ('fixed','adaptive'):
            for name in outer_names:
                names = NAMES if name=='all24' else BASELINE if name=='baseline3' else choices[mode] if name=='selected_inner' else [n for n in NAMES if n not in FAMILIES[name.removeprefix('without_')]]
                r = run_block(data,start,end,names,mode=='adaptive',spec); fit_count+=1
                key = mode+'/'+name; metrics[key] = r['metrics']
                fits.append({'block':block['name'],'model':key,**r['fit']})
                pooled[key].extend((p['p'],p['y']) for p in r['records'])
                traces.extend({'block':block['name'],'model':key,**p} for p in r['records'])
                if base_records is None:
                    base_records = r['records']
        for key,values in (('constant_p0_5',[(.5,r['y']) for r in base_records]),
                           ('persistence',[(.55 if data['y'][r['cutoff_index']] else .45,r['y']) for r in base_records])):
            metrics[key] = aggregate(values); pooled[key].extend(values)
        blocks.append({'name':block['name'],'test':block['test'],'metrics':metrics})
    if fit_count!=spec['max_fits_per_pass']:
        raise ValueError('Presupuesto de fits incumplido.')
    return {'blocks':blocks,'selections':selections, 'outer_fit_audit':fits,'fits_per_pass':fit_count,
            'pooled':{k:aggregate(v) for k,v in pooled.items()},'outer_predictions':traces,
            'winner_promoted':False,'historically_pristine_holdout':False}
