"""Evalúa solo predicción de velas primarias del artifact fijado. Sin cuentas/PnL."""
import argparse
import hashlib
import json
from pathlib import Path

from microtrade.engine import parse_csv
from microtrade.online import canonical, observed_features
from microtrade.reference_online import replay_predictive
from scripts.audit_primary_bundle import audit_bundle


def intraday_label(bars, i):
    return int(bars[i].close > bars[i].open)


def validate_artifact(metadata, source):
    expected = {'id': source['artifact_id'], 'name': source['artifact_name'], 'digest': source['artifact_digest'], 'expired': False}
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError('Artifact no coincide con protocolo o está expirado.')
    run = metadata.get('workflow_run', {})
    if run.get('id') != source['acquisition_run_id'] or run.get('head_sha') != source['revision']:
        raise ValueError('Procedencia CI incorrecta.')


def run(package, metadata, spec, output):
    validate_artifact(metadata, spec['source'])
    directory = package/'data/primary_import'
    plan = json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'], plan['end']] != spec['data_window'] or plan['symbol'] != 'BTCUSDT':
        raise ValueError('Ventana/símbolo diferente.')
    audit = audit_bundle(directory, plan, compare_mirror=False)
    if audit['status'] != 'CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':
        raise ValueError('Paquete no supera reauditoría: '+audit['status'])
    # Revisión explícita y acotada de procedencia; NO activar el gate económico.
    for name in ('BINANCE_TERMS.md', 'ATTRIBUTION.txt'):
        if not (directory/name).is_file():
            raise ValueError('Faltan términos/atribución del paquete.')
    raw = Path(audit['candidate_csv']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != audit['candidate_csv_sha256']:
        raise ValueError('CSV candidato alterado.')
    bars = parse_csv(raw.decode())
    if len(bars) != audit['expected_rows']:
        raise ValueError('Conteo normalizado incorrecto.')
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for attempt in (1, 2):
        result = replay_predictive(bars, spec, output/f'events_{attempt}.jsonl', observed_features,
                                   intraday_label, 'Binance_Vision_original_archives_verified_CI_chain')
        (output/f'full_result_{attempt}.json').write_text(canonical(result))
        results.append(result)
    if results[0]['metrics'] != results[1]['metrics'] or results[0]['initial_snapshot_sha256'] != results[1]['initial_snapshot_sha256']:
        raise ValueError('Reproducción no determinista.')
    result = results[0]
    summary = {key: result[key] for key in ('metrics', 'audit', 'initial_snapshot_sha256', 'first_target', 'last_target')}
    summary.update({'experiment_id': spec['id'], 'source': spec['source'], 'data_rows': len(bars),
                    'data_window': spec['data_window'], 'candidate_csv_sha256': audit['candidate_csv_sha256'],
                    'archive_audit': {k: audit[k] for k in ('status', 'expected_archives', 'valid_archives', 'expected_rows',
                                                          'observed_rows', 'missing_dates', 'extra_dates', 'errors')},
                    'repeated_metrics_equal': True, 'prediction_source_provenance_review': 'Pinned acquisition run and artifact, original HTTPS receipts and hashes reaudited; predictive research only.',
                    'trading_backtest': False, 'execution_costs_verified': False,
                    'point_in_time_publication_verified': False, 'market_run_enabled': False,
                    'mirror_comparison_performed': False, 'winner_selected': False,
                    'code_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                                    ('microtrade/online.py', 'microtrade/reference_online.py', 'scripts/run_primary_predictive.py')},
                    'spec_sha256': hashlib.sha256(canonical(spec).encode()).hexdigest(),
                    'license': spec['source']['license']})
    (output/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    (output/'input_audit.json').write_text(json.dumps(audit, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('data/primary_predictive_run'))
    args = parser.parse_args()
    spec = json.loads(Path('experiments/binance_primary_predictive.json').read_text())
    summary = run(args.package, json.loads(args.metadata.read_text()), spec, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
