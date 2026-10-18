"""Búsqueda temporal anidada, predictiva exclusivamente. Sin cuentas ni órdenes."""
import math
import statistics
from dataclasses import dataclass

from .online import aggregate, observed_features, probability, scores, state_hash


@dataclass
class Prepared:
    dates: list
    x: list
    y: list


def prepare(bars):
    return Prepared([b.date for b in bars], [observed_features(bars, i) if i >= 20 else None for i in range(len(bars))],
                    [int(b.close > b.open) for b in bars])


def regularized_step(weights, x, y, rate, l2):
    p = probability(weights, x)
    return [w-rate*((p-y)*v+(l2*w if j else 0)) for j, (w, v) in enumerate(zip(weights, x))]


def run_block(data, start, end, params, adaptive, epochs=10, min_rows=60, ledger=None, context=''):
    """Score targets start..end, fit at cutoff start-2. Updates only matured forecasts."""
    delay = 2; cutoff = start-delay
    if cutoff < 22 or end >= len(data.dates) or start > end:
        raise ValueError('Bloque inválido o sin warmup.')
    eligible = list(range(20, cutoff-delay+1))[-params['window']:]
    if len(eligible) < min_rows:
        raise ValueError('Entrenamiento insuficiente; no completar con datos futuros.')
    weights = [0.0]*4
    for _ in range(epochs):
        for j in eligible:
            weights = regularized_step(weights, data.x[j], data.y[j+delay], params['learning_rate'], params['l2'])
    fit = {'forecast_cutoff': data.dates[cutoff], 'last_training_feature': data.dates[eligible[-1]],
           'last_training_label': data.dates[eligible[-1]+delay], 'effective_training_rows': len(eligible),
           'first_training_feature': data.dates[eligible[0]], 'params': dict(params), 'initial_hash': state_hash(weights)}
    if ledger:
        ledger.append({'type': 'initial_fit', 'context': context, **fit, 'weights': list(weights), 'adaptive': adaptive})
    pending = {}; records = []
    for i in range(cutoff, end+1):
        if i in pending:
            prediction = pending.pop(i); p = prediction['p']; y = data.y[i]
            records.append({'target': data.dates[i], 'cutoff': data.dates[prediction['cutoff_index']],
                            'p': p, 'y': y, 'persistence': prediction['persistence']})
            if ledger:
                ledger.append({'type': 'outcome', 'context': context, 'target_index': i,
                               'prediction_id': prediction['id'], 'y': y, 'p_original': p, 'scores': scores(p, y)})
            if adaptive:
                before = state_hash(weights)
                weights = regularized_step(weights, prediction['features'], y, params['learning_rate'], params['l2'])
                if ledger:
                    ledger.append({'type': 'update', 'context': context, 'asof_index': i,
                                   'prediction_id': prediction['id'], 'before': before,
                                   'after': state_hash(weights), 'weights': list(weights)})
        target = i+delay
        if start <= target <= end:
            prediction = {'id': f'{context}:{i}', 'cutoff_index': i, 'features': data.x[i],
                          'p': probability(weights, data.x[i]), 'persistence': .55 if data.y[i] else .45}
            if ledger:
                ledger.append({'type': 'prediction', 'context': context, 'prediction_id': prediction['id'],
                               'cutoff_index': i, 'target_index': target, 'cutoff': data.dates[i],
                               'target': data.dates[target], 'features': data.x[i], 'p': prediction['p'],
                               'persistence': prediction['persistence'], 'weights': list(weights), 'snapshot': state_hash(weights)})
            pending[target] = prediction
    if pending or len(records) != end-start+1:
        raise ValueError('Pronósticos pendientes o cobertura de etiquetas incorrecta.')
    return {'records': records, 'fit': fit, 'metrics': aggregate([(r['p'], r['y']) for r in records])}


def tune(past, inner, mode, spec, seed):
    import optuna
    if mode not in ('fixed', 'adaptive'):
        raise ValueError('Modo desconocido.')
    mapping = {d: i for i, d in enumerate(past.dates)}
    for start, end in inner:
        if start not in mapping or end not in mapping or start > end:
            raise ValueError('Validación interna fuera de los datos disponibles para selección.')
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed, n_startup_trials=2, multivariate=False)
    study = optuna.create_study(direction='minimize', sampler=sampler, pruner=optuna.pruners.NopPruner())
    space = spec['search_space']

    def objective(trial):
        params = {key: trial.suggest_float(key, space[key]['low'], space[key]['high'], log=True)
                  for key in ('learning_rate', 'l2')}
        params['window'] = trial.suggest_categorical('window', space['window'])
        results = [run_block(past, mapping[start], mapping[end], params, mode == 'adaptive',
                             spec['initial_training_epochs'], spec['minimum_training_rows']) for start, end in inner]
        losses = [r['metrics']['log_loss'] for r in results]
        counts = [r['metrics']['n'] for r in results]
        trial.set_user_attr('fold_losses', losses)
        trial.set_user_attr('fold_n', counts)
        trial.set_user_attr('effective_training_rows', [r['fit']['effective_training_rows'] for r in results])
        trial.set_user_attr('last_training_labels', [r['fit']['last_training_label'] for r in results])
        trial.set_user_attr('fold_loss_std_descriptive', statistics.pstdev(losses))
        return sum(n*loss for n, loss in zip(counts, losses))/sum(counts)

    study.optimize(objective, n_trials=spec['trial_budget']['per_model_per_outer_block'], n_jobs=1)
    trials = [{'number': t.number, 'params': t.params, 'value': t.value, **t.user_attrs} for t in study.trials]
    if len(trials) != spec['trial_budget']['per_model_per_outer_block'] or any(not math.isfinite(t['value']) for t in trials):
        raise ValueError('Búsqueda incompleta; no esconder intentos fallidos.')
    best = min(trials, key=lambda t: (t['value'], t['number']))
    return {'selected_trial': best['number'], 'selected_params': best['params'], 'inner_loss': best['value'],
            'trials': trials, 'seed': seed, 'selection_data_last_date': past.dates[-1]}


def run_nested(bars, spec, ledger=None):
    budget = spec['trial_budget']
    if spec['models'] != ['fixed', 'adaptive'] or not 1 <= budget['total'] <= 30 or len(spec['outer_blocks'])*2*budget['per_model_per_outer_block'] != budget['total']:
        raise ValueError('Presupuesto/modelos fuera del protocolo: máximo 30 intentos.')
    data = prepare(bars); index = {d: i for i, d in enumerate(data.dates)}
    pooled = {name: [] for name in ('fixed_tuned','adaptive_tuned','fixed_untuned','adaptive_untuned','constant_p0_5','persistence')}
    blocks = []; selections = []; traces = []
    for k, block in enumerate(spec['outer_blocks']):
        start, end = (index[d] for d in block['test']); cutoff = start-2
        if max(end_ for _, end_ in block['inner']) > data.dates[cutoff]:
            raise ValueError('Validación interna invade el momento de decisión externa.')
        if blocks and block['test'][0] <= blocks[-1]['test'][1]:
            raise ValueError('Bloques externos solapados o desordenados.')
        # El optimizador recibe un prefijo separado; ninguna etiqueta externa entra en objective.
        past = prepare(bars[:cutoff+1]); block_metrics = {}; fits = {}; choices = {}
        for m, mode in enumerate(('fixed','adaptive')):
            chosen = tune(past, block['inner'], mode, spec, spec['trial_budget']['seed_base']+2*k+m)
            selections.append({'block': block['name'], 'mode': mode, **chosen})
            choices[mode] = chosen
            if ledger:
                ledger.append({'type': 'selection', 'block': block['name'], 'mode': mode,
                               'selected_trial': chosen['selected_trial'], 'params': chosen['selected_params'],
                               'latest_data': past.dates[-1], 'first_outer_target': data.dates[start]})
        # Freeze both selections before evaluating either mode on this outer block.
        for mode in ('fixed', 'adaptive'):
            chosen = choices[mode]
            for suffix, params in (('tuned', chosen['selected_params']), ('untuned', spec['controls']['untuned_fixed_adaptive'])):
                name = mode+'_'+suffix
                result = run_block(data, start, end, params, mode == 'adaptive', spec['initial_training_epochs'],
                                   spec['minimum_training_rows'], ledger, block['name']+'/'+name)
                block_metrics[name] = result['metrics']; fits[name] = result['fit']
                pooled[name].extend((r['p'], r['y']) for r in result['records'])
                traces.extend({'block': block['name'], 'model': name, **r} for r in result['records'])
                if name == 'fixed_untuned':
                    control_records = result['records']
        for name, probs in (('constant_p0_5', [(.5, r['y']) for r in control_records]),
                            ('persistence', [(r['persistence'], r['y']) for r in control_records])):
            pooled[name].extend(probs); block_metrics[name] = aggregate(probs)
        blocks.append({'name': block['name'], 'test': block['test'], 'selection_cutoff': past.dates[-1],
                       'metrics': block_metrics, 'fit_audit': fits})
    actual = sum(len(s['trials']) for s in selections)
    if actual != spec['trial_budget']['total']:
        raise ValueError('Presupuesto global inconsistente.')
    return {'blocks': blocks, 'selections': selections, 'total_trials': actual,
            'pooled_outer_metrics': {name: aggregate(rows) for name, rows in pooled.items()},
            'outer_predictions': traces, 'trading_backtest': False, 'winner_promoted': False,
            'historically_pristine_holdout': False}
