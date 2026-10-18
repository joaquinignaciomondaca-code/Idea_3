"""Comprueba cadena local y semántica causal del ledger externo de búsqueda anidada."""
import hashlib
import json
from pathlib import Path
from .nested_search import prepare, regularized_step
from .online import canonical, probability, scores, state_hash


def verify_nested_ledger(path, bars):
    data = prepare(bars); index = {d: i for i, d in enumerate(data.dates)}
    previous = '0'*64; states = {}; predictions = {}; outcomes = {}; updated = set(); count = 0
    for sequence, line in enumerate(Path(path).read_text().splitlines()):
        item = json.loads(line); sha = item.pop('sha256')
        if item['sequence'] != sequence or item['previous_sha256'] != previous or hashlib.sha256(canonical(item).encode()).hexdigest() != sha:
            raise ValueError('Cadena de auditoría inválida.')
        previous = sha; e = item['event']; kind = e['type']; count += 1
        if kind == 'selection':
            if e['latest_data'] >= e['first_outer_target']:
                raise ValueError('Selección usa datos externos.')
            continue
        context = e['context']
        if kind == 'initial_fit':
            if context in states or e['last_training_label'] > e['forecast_cutoff']:
                raise ValueError('Fit repetido o etiqueta de entrenamiento futura.')
            if state_hash(e['weights']) != e['initial_hash']:
                raise ValueError('Snapshot inicial incorrecto.')
            states[context] = {'weights': e['weights'], 'params': e['params'], 'adaptive': e['adaptive'],
                               'last_index': index[e['forecast_cutoff']]}
            continue
        if context not in states:
            raise ValueError('Evento sin fit previo.')
        state = states[context]
        i = e['cutoff_index'] if kind == 'prediction' else e['target_index'] if kind == 'outcome' else e['asof_index']
        if i < state['last_index']:
            raise ValueError('Orden temporal inválido.')
        state['last_index'] = i; key = e['prediction_id']
        if kind == 'prediction':
            if key in predictions or e['target_index'] != i+2 or e['features'] != data.x[i]:
                raise ValueError('Predicción duplicada, features futuras o horizonte incorrecto.')
            if e['weights'] != state['weights'] or state_hash(state['weights']) != e['snapshot'] or e['p'] != probability(state['weights'], data.x[i]):
                raise ValueError('Predicción no corresponde a pesos disponibles.')
            predictions[key] = e
        elif kind == 'outcome':
            if key not in predictions or key in outcomes:
                raise ValueError('Resultado sin pronóstico o repetido.')
            p = predictions[key]
            if p['context'] != context or p['target_index'] != i or e['y'] != data.y[i] or e['p_original'] != p['p'] or e['scores'] != scores(p['p'], e['y']):
                raise ValueError('Etiqueta/score no corresponde a la predicción original.')
            outcomes[key] = e
        elif kind == 'update':
            if not state['adaptive'] or key not in outcomes or key in updated or outcomes[key]['target_index'] != i:
                raise ValueError('Actualización sin feedback posterior o inválida.')
            expected = regularized_step(state['weights'], predictions[key]['features'], outcomes[key]['y'],
                                        state['params']['learning_rate'], state['params']['l2'])
            if e['before'] != state_hash(state['weights']) or e['weights'] != expected or e['after'] != state_hash(expected):
                raise ValueError('Actualización inconsistente.')
            state['weights'] = expected; updated.add(key)
        else:
            raise ValueError('Tipo desconocido.')
    if not count or set(predictions) != set(outcomes):
        raise ValueError('Ledger vacío o resultados pendientes.')
    adaptive_keys = {key for key, p in predictions.items() if states[p['context']]['adaptive']}
    if updated != adaptive_keys:
        raise ValueError('Faltan actualizaciones adaptativas.')
    return {'events': count, 'predictions': len(predictions), 'outcomes': len(outcomes),
            'updates': len(updated), 'last_event_sha256': previous,
            'attestation': 'Local chain and replay semantics checked; not external time attestation.'}
