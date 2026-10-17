"""Circuito causal mínimo, SOLO replay sintético mientras el gate primario esté cerrado."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .engine import Config, simulate


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def state_hash(weights):
    return hashlib.sha256(canonical(weights).encode()).hexdigest()


def probability(weights, x):
    z = max(-35, min(35, sum(w*v for w, v in zip(weights, x))))
    return 1/(1+math.exp(-z))


def update(weights, x, y, rate):
    p = probability(weights, x)
    return [w-rate*(p-y)*v for w, v in zip(weights, x)]


def observed_features(bars, i):
    return numeric_features([b.close for b in bars[:i+1]], i)


def numeric_features(values, i):
    if i < 20:
        raise ValueError('Se requieren 20 retornos previos.')
    closes = values[i-20:i+1]
    values = [math.log(closes[-1]/closes[-2])*100,
              math.log(closes[-1]/closes[-6])*20,
              statistics.pstdev(math.log(closes[j]/closes[j-1]) for j in range(1, 21))*100]
    return [1.0] + [max(-5.0, min(5.0, v)) for v in values]


def scores(p, y):
    q = max(1e-12, min(1-1e-12, p))
    return {'brier': (p-y)**2, 'log_loss': -(y*math.log(q)+(1-y)*math.log1p(-q)),
            'correct': int((p > .5) == bool(y))}


class Ledger:
    """Archivo de creación exclusiva; append hash-chain, sin método de reescritura.

    No es un timestamp externo ni impide que un administrador borre archivos.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('x', encoding='utf-8')
        self.previous = '0'*64
        self.sequence = 0

    def append(self, event):
        body = {'sequence': self.sequence, 'previous_sha256': self.previous,
                'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'event': event}
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        self.file.write(canonical({**body, 'sha256': digest})+'\n')
        self.file.flush()
        self.previous = digest
        self.sequence += 1

    def close(self):
        self.file.close()


def verify_ledger(path, bars=None, feature_builder=None, label_builder=None):
    previous = '0'*64
    predictions, outcomes, states = {}, set(), {}
    rate = delay = None
    count = 0
    last_index = -1
    with Path(path).open() as stream:
        for sequence, line in enumerate(stream):
            item = json.loads(line)
            digest = item.pop('sha256')
            if item['sequence'] != sequence or item['previous_sha256'] != previous:
                raise ValueError('Secuencia/cadena inválida.')
            if hashlib.sha256(canonical(item).encode()).hexdigest() != digest:
                raise ValueError('Hash de evento inválido.')
            previous = digest
            event = item['event']; kind = event['type']
            if kind == 'initial_state':
                if sequence != 0:
                    raise ValueError('Estado inicial fuera de orden.')
                rate, delay = event['learning_rate'], event['delay']
                states = {model: list(event['weights']) for model in ('fixed', 'adaptive')}
                last_index = event['training_end_index']
                if event['last_training_label_index'] > last_index:
                    raise ValueError('Etiqueta de entrenamiento futura.')
            elif kind in ('prediction', 'outcome', 'update'):
                index = event['asof_index']
                if index < last_index or not states:
                    raise ValueError('Evento fuera de orden temporal.')
                last_index = index
                model = event['model']
                if model not in states:
                    raise ValueError('Modelo desconocido.')
                if kind == 'prediction':
                    key = event['prediction_id']
                    if key in predictions or event['target_index'] != index+delay:
                        raise ValueError('Predicción duplicada o horizonte incorrecto.')
                    if event['snapshot_sha256'] != state_hash(states[model]) or event['weights'] != states[model]:
                        raise ValueError('Snapshot no corresponde al modelo disponible.')
                    if not math.isclose(event['p_up'], probability(event['weights'], event['features']), abs_tol=1e-14):
                        raise ValueError('Probabilidad no corresponde al snapshot.')
                    if bars is not None and (event['features'] != (feature_builder or observed_features)(bars, index) or
                                            event['feature_cutoff_session'] != bars[index].date or
                                            event['target_session'] != bars[index+delay].date):
                        raise ValueError('Features/fechas no corresponden al input observado.')
                    predictions[key] = event
                elif kind == 'outcome':
                    key = event['prediction_id']
                    if key not in predictions or key in outcomes:
                        raise ValueError('Resultado sin predicción previa o duplicado.')
                    forecast = predictions[key]
                    if forecast['target_index'] != index or forecast['model'] != model or event['y'] not in (0, 1):
                        raise ValueError('Resultado anticipado o modelo/etiqueta incorrectos.')
                    if bars is not None and event['y'] != (label_builder(bars, index) if label_builder else int(bars[index].close > bars[index].open)):
                        raise ValueError('Etiqueta distinta de la sesión observada.')
                    expected = scores(forecast['p_up'], event['y'])
                    if event['scores'] != expected:
                        raise ValueError('Scores no corresponden a la predicción original.')
                    outcomes.add(key)
                    outcomes_data[key] = event
                else:
                    key = event['prediction_id']
                    if model != 'adaptive' or key not in outcomes or key in updates:
                        raise ValueError('Actualización antes de feedback o repetida.')
                    if outcomes_data[key]['asof_index'] != index or event['before_sha256'] != state_hash(states[model]):
                        raise ValueError('Actualización no corresponde al estado/evento actual.')
                    expected = update(states[model], predictions[key]['features'], outcomes_data[key]['y'], rate)
                    if expected != event['after_weights']:
                        raise ValueError('Actualización matemática incorrecta.')
                    states[model] = expected
                    updates.add(key)
            else:
                raise ValueError('Evento desconocido.')
            count += 1
            if sequence == 0:
                outcomes_data, updates = {}, set()
    if not count or set(predictions) != outcomes:
        raise ValueError('Ledger vacío o predicciones sin resolver.')
    adaptive_outcomes = {k for k, p in predictions.items() if p['model'] == 'adaptive'}
    if updates != adaptive_outcomes:
        raise ValueError('Faltan actualizaciones adaptativas.')
    return {'events': count, 'predictions': len(predictions), 'outcomes': len(outcomes),
            'adaptive_updates': len(updates), 'last_event_sha256': previous,
            'integrity': 'local_hash_chain_and_causal_event_order_verified_not_external_attestation'}


def aggregate(records):
    n = len(records)
    bins = []
    for j in range(5):
        rows = [(p, y) for p, y in records if min(4, int(p*5)) == j]
        if rows:
            bins.append({'lower': j/5, 'upper': (j+1)/5, 'n': len(rows),
                         'mean_probability': statistics.mean(p for p, _ in rows),
                         'observed_frequency': statistics.mean(y for _, y in rows)})
    return {'n': n, 'brier': statistics.mean(scores(p, y)['brier'] for p, y in records),
            'log_loss': statistics.mean(scores(p, y)['log_loss'] for p, y in records),
            'accuracy': statistics.mean(scores(p, y)['correct'] for p, y in records),
            'ece_5_bins_descriptive': sum(b['n']/n*abs(b['mean_probability']-b['observed_frequency']) for b in bins),
            'calibration_bins': bins}


def replay_synthetic(bars, spec, ledger_path):
    """Entrada explícitamente sintética. No hay función que apruebe datos de mercado."""
    train_end, delay = spec['initial_training_end_index'], spec['target_delay_sessions']
    rate = spec['learning_rate']
    if train_end < 40 or delay != 2 or len(bars) <= train_end+delay+10:
        raise ValueError('Historia insuficiente o delay no implementado.')
    weights = [0.0]*4
    for _ in range(spec['initial_training_epochs']):
        for j in range(20, train_end-delay+1):
            y = int(bars[j+delay].close > bars[j+delay].open)
            weights = update(weights, observed_features(bars, j), y, rate)
    states = {model: list(weights) for model in ('fixed', 'adaptive')}
    versions = {'fixed': 0, 'adaptive': 0}
    pending, records = {}, {'fixed': [], 'adaptive': []}
    signals = {'fixed': {}, 'adaptive': {}}
    ledger = Ledger(ledger_path)
    try:
        ledger.append({'type': 'initial_state', 'weights': weights, 'training_end_index': train_end,
                       'last_training_label_index': train_end, 'learning_rate': rate, 'delay': delay,
                       'source': 'synthetic_software_test_not_market_data'})
        for i in range(train_end, len(bars)):
            # Se puntúa SIEMPRE la probabilidad guardada, no se recalcula con pesos actualizados.
            for forecast in pending.pop(i, []):
                model = forecast['model']; y = int(bars[i].close > bars[i].open)
                ledger.append({'type': 'outcome', 'model': model, 'asof_index': i,
                               'simulated_asof_session': bars[i].date, 'availability': 'after_session_close',
                               'prediction_id': forecast['prediction_id'], 'y': y,
                               'scores': scores(forecast['p_up'], y)})
                records[model].append((forecast['p_up'], y))
                if model == 'adaptive':
                    before = state_hash(states[model])
                    states[model] = update(states[model], forecast['features'], y, rate)
                    versions[model] += 1
                    ledger.append({'type': 'update', 'model': model, 'asof_index': i,
                                   'prediction_id': forecast['prediction_id'], 'before_sha256': before,
                                   'after_weights': states[model], 'model_version': versions[model]})
            if i+delay < len(bars):
                x = observed_features(bars, i)
                for model in states:
                    p = probability(states[model], x)
                    forecast = {'type': 'prediction', 'model': model, 'model_version': versions[model],
                                'prediction_id': f'{model}:{i}', 'asof_index': i,
                                'simulated_asof_session': bars[i].date, 'availability': 'after_session_close',
                                'target_index': i+delay, 'target_session': bars[i+delay].date,
                                'feature_cutoff_session': bars[i].date, 'features': x,
                                'weights': list(states[model]), 'snapshot_sha256': state_hash(states[model]), 'p_up': p}
                    ledger.append(forecast)
                    pending.setdefault(i+delay, []).append(forecast)
                    signals[model][bars[i].date] = p > .55
    finally:
        ledger.close()
    audit = verify_ledger(ledger_path, bars=bars)
    costs = spec['cost_profile']
    cfg = Config(capital=costs['capital'], window=20, cadence=1, delay_bars=delay-1,
                 fee_pct=costs['fee_pct_each_side'], spread_bps=costs['spread_full_bps'],
                 slippage_bps=costs['slippage_each_side_bps'], min_order=costs['min_order'],
                 min_qty=costs['min_qty'], qty_step=costs['qty_step'])
    start = bars[train_end+delay].date
    accounts = {model: simulate(bars, cfg, strategy='external', start_date=start, signals=signal)
                for model, signal in signals.items()}
    accounts['hold'] = simulate(bars, cfg, strategy='hold', start_date=start)
    return {'prediction_metrics': {model: aggregate(rows) for model, rows in records.items()} |
                                  {'constant_p_0_5': aggregate([(.5, y) for _, y in records['fixed']])},
            'audit': audit, 'accounts': accounts,
            'initial_snapshot_sha256': state_hash(weights), 'source': 'SYNTHETIC_NOT_MARKET_EVIDENCE',
            'evaluation_start': start, 'evaluation_end': bars[-1].date,
            'selection': 'No winner selection. Fixed vs adaptive procedure test only.'}
