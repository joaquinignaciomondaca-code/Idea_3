"""Publica solo agregados acotados por GitHub Checks, nunca velas/ledgers/secrets."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def check_payload(summary, head_sha, run_url):
    if summary.get('experiment_id') != 'BINANCE-PRIMARY-PREDICTIVE-001' or summary.get('trading_backtest') is not False:
        raise ValueError('Resumen no permitido.')
    allowed = {'experiment_id','source','data_rows','data_window','candidate_csv_sha256','archive_audit',
               'metrics','audit','initial_snapshot_sha256','first_target','last_target','repeated_metrics_equal',
               'prediction_source_provenance_review','trading_backtest','execution_costs_verified',
               'point_in_time_publication_verified','market_run_enabled','mirror_comparison_performed',
               'winner_selected','code_sha256','spec_sha256','license'}
    if set(summary)-allowed:
        raise ValueError('Campos no agregados o desconocidos; no se publican.')
    text = json.dumps(summary, sort_keys=True, indent=2, allow_nan=False)
    if len(text.encode()) > 60000:
        raise ValueError('Resumen supera el límite; no truncar resultados silenciosamente.')
    return {'name': 'Primary predictive replay — aggregate report', 'head_sha': head_sha,
            'status': 'completed', 'conclusion': 'success', 'details_url': run_url,
            'output': {'title': 'Official candle prediction diagnostic — no trading approval',
                       'summary': 'Pinned Binance archives reaudited; fixed/adaptive predictions repeated exactly. Noncommercial retrospective research only.',
                       'text': '```json\n'+text+'\n```'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    repo, sha, run_id = (os.environ[k] for k in ('GITHUB_REPOSITORY','GITHUB_SHA','GITHUB_RUN_ID'))
    payload = check_payload(json.loads(args.summary.read_text()), sha, f'https://github.com/{repo}/actions/runs/{run_id}')
    # GH_TOKEN is scoped by Actions; never print it or put it in the payload.
    response = subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],
                              input=json.dumps(payload),text=True,capture_output=True,check=True)
    check = json.loads(response.stdout)
    print(json.dumps({'check_id': check['id'], 'url': check['html_url']}))


if __name__ == '__main__':
    main()
