"""Publica agregados completos de importancia; no series ni aprobación económica."""
import json
import os
import subprocess
from pathlib import Path
from microtrade.online import canonical

CHECK_NAME = 'Feature ablation — aggregate report'


def payload(s,sha):
    allowed = {'experiment_id','spec_sha256','source','data_rows','extended_data_sha256','source_audit','reproduced',
               'trading_backtest','costs_verified','market_run_enabled','historically_pristine_holdout','winner_promoted',
               'fits_per_pass','passes','hpo_trials','environment','selections','pooled','blocks','full_result_sha256','code_sha256','license'}
    if set(s)-allowed or s.get('experiment_id')!='FEATURE-ABLATION-001' or s.get('reproduced') is not True:
        raise ValueError('Resumen no autorizado.')
    if any(s.get(k) is not False for k in ('trading_backtest','costs_verified','market_run_enabled','historically_pristine_holdout','winner_promoted')):
        raise ValueError('Fuera del alcance predictivo retrospectivo.')
    if s.get('fits_per_pass')!=390 or s.get('passes')!=2 or s.get('hpo_trials')!=0 or len(s['selections'])!=6:
        raise ValueError('Presupuesto/selecciones incompletos.')
    if any(len(c['feature_importance'])!=24 or len(c['family_importance'])!=4 for c in s['selections']):
        raise ValueError('Ablaciones omitidas.')
    text = canonical(s)
    if len(text.encode())>60000:
        raise ValueError('No truncar resultados.')
    return {'name':CHECK_NAME,'head_sha':sha,'status':'completed','conclusion':'success',
            'output':{'title':'24-feature diagnostic completed, no trading approval',
                      'summary':'390 prescribed fits per pass, repeated identically; inner-only selection, all external models reported.',
                      'text':'```json\n'+text+'\n```'}}


def main():
    s=json.loads(Path('data/feature_study_run/summary.json').read_text())
    body=payload(s,os.environ['GITHUB_SHA']); repo=os.environ['GITHUB_REPOSITORY']
    r=subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],input=json.dumps(body),text=True,capture_output=True,check=True)
    check=json.loads(r.stdout); print(json.dumps({'id':check['id'],'url':check['html_url']}))


if __name__=='__main__':
    main()
