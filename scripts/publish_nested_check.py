"""Publica únicamente agregados de la búsqueda y el registro de sus 30 intentos."""
import json
import os
import subprocess
from pathlib import Path

CHECK_NAME = 'Nested Optuna predictive — aggregate report'


def payload(summary, head_sha):
    allowed = {'experiment_id','source','spec_sha256','data_sha256','data_rows','source_audit','results','audit',
               'reproduced','trading_backtest','costs_verified','market_run_enabled','environment','code_sha256','license'}
    if set(summary)-allowed or summary.get('experiment_id') != 'NESTED-OPTUNA-PREDICTIVE-001':
        raise ValueError('Resumen no autorizado.')
    if summary.get('reproduced') is not True or summary.get('trading_backtest') is not False or summary.get('market_run_enabled') is not False:
        raise ValueError('Estado fuera del alcance permitido.')
    result = summary['results']
    if 'outer_predictions' in result or result['total_trials'] != 30 or sum(len(s['trials']) for s in result['selections']) != 30:
        raise ValueError('Faltan trials o se incluyeron predicciones individuales.')
    text = json.dumps(summary, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(text.encode()) > 60000:
        raise ValueError('Excede límite; no truncar resultados.')
    return {'name': CHECK_NAME, 'head_sha': head_sha, 'status': 'completed', 'conclusion': 'success',
            'output': {'title': 'Nested TPE diagnostic completed; no trading approval',
                       'summary': '30 trials selected only on temporal inner validation; two identical complete searches. Noncommercial predictive research.',
                       'text': '```json\n'+text+'\n```'}}


def main():
    summary = json.loads(Path('data/nested_optuna_run/summary.json').read_text())
    body = payload(summary, os.environ['GITHUB_SHA'])
    repo = os.environ['GITHUB_REPOSITORY']
    output = subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],
                            input=json.dumps(body),text=True,capture_output=True,check=True)
    check = json.loads(output.stdout)
    print(json.dumps({'check_id': check['id'], 'url': check['html_url']}))


if __name__ == '__main__':
    main()
