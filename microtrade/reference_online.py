"""Predicción de una métrica de referencia. Sin OHLC inventado, cuentas ni órdenes."""
import csv
import io
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .online import Ledger, aggregate, numeric_features, probability, scores, state_hash, update, verify_ledger


@dataclass(frozen=True)
class ReferencePoint:
    date: str
    value: Decimal


def parse_reference(raw):
    reader = csv.DictReader(io.StringIO(raw.decode()))
    if reader.fieldnames != ['date', 'value']:
        raise ValueError('Se requiere date,value, no velas.')
    points = []; previous = None
    for row in reader:
        day = date.fromisoformat(row['date']); value = Decimal(row['value'])
        if not value.is_finite() or value <= 0 or (previous and day-previous != timedelta(days=1)):
            raise ValueError('Precio inválido, duplicado, desorden o hueco.')
        points.append(ReferencePoint(day.isoformat(), value)); previous = day
    return points


def reference_features(points, i):
    return numeric_features([p.value for p in points[:i+1]], i)


def reference_label(points, i):
    return int(points[i].value > points[i-1].value)


def replay_reference(points, spec, ledger_path):
    return replay_predictive(points, spec, ledger_path, reference_features, reference_label,
                             'CoinMetrics_original_published_PriceUSD_not_exchange_candles')


def replay_predictive(points, spec, ledger_path, feature_builder, label_builder, source_name):
    index = {p.date: i for i, p in enumerate(points)}
    train_end = index[spec['initial_training_through']]
    first = index[spec['forecast_cutoff_start']]
    delay, rate = spec['target_delay_sessions'], spec['learning_rate']
    if first <= train_end or train_end < 40 or delay != 2 or len(points) < first+delay+1:
        raise ValueError('Corte/ventana insuficiente o delay no soportado.')
    weights = [0.0]*4
    for _ in range(spec['initial_training_epochs']):
        for j in range(20, train_end-delay+1):
            weights = update(weights, feature_builder(points, j), label_builder(points, j+delay), rate)
    states = {model: list(weights) for model in ('fixed', 'adaptive')}
    versions = {model: 0 for model in states}
    pending = {}; observations = []
    ledger = Ledger(ledger_path)
    try:
        ledger.append({'type': 'initial_state', 'weights': weights, 'training_end_index': train_end,
                       'last_training_label_index': train_end, 'learning_rate': rate, 'delay': delay,
                       'source': source_name,
                       'label_definition': spec['label'], 'source_revision': spec['source']['revision']})
        for i in range(first, len(points)):
            for forecast in pending.pop(i, []):
                model = forecast['model']; y = label_builder(points, i)
                ledger.append({'type': 'outcome', 'model': model, 'asof_index': i,
                               'simulated_asof_session': points[i].date, 'availability': 'reconstructed_metric_day_end_not_verified_publication_time',
                               'prediction_id': forecast['prediction_id'], 'y': y,
                               'scores': scores(forecast['p_up'], y)})
                observations.append({'model': model, 'target_date': points[i].date, 'y': y,
                                     'p_up': forecast['p_up'], 'p_persistence': forecast['p_persistence']})
                if model == 'adaptive':
                    before = state_hash(states[model])
                    states[model] = update(states[model], forecast['features'], y, rate)
                    versions[model] += 1
                    ledger.append({'type': 'update', 'model': model, 'asof_index': i,
                                   'prediction_id': forecast['prediction_id'], 'before_sha256': before,
                                   'after_weights': states[model], 'model_version': versions[model]})
            if i+delay < len(points):
                x = feature_builder(points, i)
                for model in states:
                    forecast = {'type': 'prediction', 'model': model, 'model_version': versions[model],
                                'prediction_id': f'{model}:{i}', 'asof_index': i,
                                'simulated_asof_session': points[i].date,
                                'availability': 'reconstructed_metric_day_end_not_verified_publication_time',
                                'target_index': i+delay, 'target_session': points[i+delay].date,
                                'feature_cutoff_session': points[i].date, 'features': x,
                                'weights': list(states[model]), 'snapshot_sha256': state_hash(states[model]),
                                'p_up': probability(states[model], x),
                                'p_persistence': .55 if label_builder(points, i) else .45}
                    ledger.append(forecast); pending.setdefault(i+delay, []).append(forecast)
    finally:
        ledger.close()
    audit = verify_ledger(ledger_path, bars=points, feature_builder=feature_builder, label_builder=label_builder)
    metrics = {}
    for epoch, (start, end) in spec['report_label_epochs'].items():
        rows = [r for r in observations if start <= r['target_date'] <= end]
        metrics[epoch] = {}
        for model in ('fixed', 'adaptive'):
            selected = [r for r in rows if r['model'] == model]
            metrics[epoch][model] = aggregate([(r['p_up'], r['y']) for r in selected])
        reference = [r for r in rows if r['model'] == 'fixed']
        metrics[epoch]['constant_p_0_5'] = aggregate([(.5, r['y']) for r in reference])
        metrics[epoch]['persistence'] = aggregate([(r['p_persistence'], r['y']) for r in reference])
        metrics[epoch]['first_target'] = reference[0]['target_date']
        metrics[epoch]['last_target'] = reference[-1]['target_date']
    return {'audit': audit, 'metrics': metrics, 'initial_snapshot_sha256': state_hash(weights),
            'first_target': observations[0]['target_date'], 'last_target': observations[-1]['target_date'],
            'observations': observations, 'trading_backtest': False,
            'execution_prices_verified': False, 'point_in_time_publication_verified': False,
            'decision': 'Retrospective prediction diagnostic only. No profitability or winner promotion.'}
