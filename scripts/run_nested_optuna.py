"""Búsqueda TPE acotada, temporal anidada, sobre el artifact primario fijado."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

from microtrade.engine import parse_csv
from microtrade.nested_search import run_nested
from microtrade.nested_audit import verify_nested_ledger
from microtrade.online import Ledger, canonical
from scripts.audit_primary_bundle import audit_bundle
from scripts.run_primary_predictive import validate_artifact


def run(package, metadata, spec, output):
    import optuna, numpy
    if optuna.__version__ != '4.5.0' or numpy.__version__ != '2.2.6':
        raise ValueError('Versiones distintas del protocolo.')
    validate_artifact(metadata, spec['source'])
    directory = package/'data/primary_import'
    plan = json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'], plan['end']] != spec['data_window'] or plan['symbol'] != 'BTCUSDT':
        raise ValueError('Plan/fuente diferente.')
    source_audit = audit_bundle(directory, plan, compare_mirror=False)
    if source_audit['status'] != 'CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':
        raise ValueError('Reauditoría de archivos primarios fallida.')
    if any(not (directory/name).is_file() for name in ('BINANCE_TERMS.md', 'ATTRIBUTION.txt')):
        raise ValueError('Términos o atribución ausentes.')
    raw = Path(source_audit['candidate_csv']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_audit['candidate_csv_sha256']:
        raise ValueError('CSV alterado.')
    bars = parse_csv(raw.decode()); output.mkdir(parents=True, exist_ok=False)
    runs = []; audits = []
    for attempt in (1, 2):
        path = output/f'outer_ledger_{attempt}.jsonl'; ledger = Ledger(path)
        try:
            result = run_nested(bars, spec, ledger)
        finally:
            ledger.close()
        audits.append(verify_nested_ledger(path, bars))
        (output/f'full_result_{attempt}.json').write_text(canonical(result))
        runs.append(result)
    if runs[0] != runs[1]:
        raise ValueError('La repetición cambió trials, selecciones, predicciones o métricas.')
    result = {k: v for k, v in runs[0].items() if k != 'outer_predictions'}
    summary = {'experiment_id': spec['id'], 'source': spec['source'],
               'spec_sha256': hashlib.sha256(canonical(spec).encode()).hexdigest(),
               'data_sha256': source_audit['candidate_csv_sha256'], 'data_rows': len(bars),
               'source_audit': {k: source_audit[k] for k in ('expected_archives','valid_archives','expected_rows','observed_rows','errors','missing_dates','extra_dates')},
               'results': result, 'audit': audits[0], 'reproduced': True, 'trading_backtest': False,
               'costs_verified': False, 'market_run_enabled': False,
               'environment': {'python': platform.python_version(), 'optuna': optuna.__version__, 'numpy': numpy.__version__},
               'code_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                               ('microtrade/nested_search.py','microtrade/nested_audit.py','microtrade/online.py','scripts/run_nested_optuna.py')},
               'license': spec['source']['license']}
    encoded = json.dumps(summary, indent=2, allow_nan=False)
    if len(canonical(summary).encode()) > 60000:
        raise ValueError('Resumen excede el límite de publicación; conservar todo y revisar formato, no truncar.')
    (output/'summary.json').write_text(encoded)
    (output/'source_audit.json').write_text(json.dumps(source_audit, indent=2))
    (output/'spec.json').write_text(canonical(spec))
    print(json.dumps({'experiment_id': spec['id'], 'trials': result['total_trials'],
                      'reproduced': True, 'pooled': result['pooled_outer_metrics']}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('data/nested_optuna_run'))
    args = parser.parse_args()
    spec = json.loads(Path('experiments/nested_optuna_predictive.json').read_text())
    run(args.package, json.loads(args.metadata.read_text()), spec, args.output)


if __name__ == '__main__':
    main()
