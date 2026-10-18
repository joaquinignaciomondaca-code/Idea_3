"""Publica resultados completos acotados; success no es aprobación financiera."""
import json
import os
import subprocess
from pathlib import Path
from microtrade.online import canonical
CHECK_NAME='Converged classifier — aggregate report'


def payload(s,sha):
    allowed={'experiment_id','source','spec_sha256','data_rows','extended_data_sha256','source_audit','results','reproduced','sgd_baseline_reproduced','passes','trading_backtest','market_run_enabled','costs_verified','environment','full_result_sha256','code_sha256'}
    if set(s)-allowed or s.get('experiment_id')!='CONVERGED-CLASSIFIER-001' or s.get('reproduced') is not True or s.get('sgd_baseline_reproduced') is not True or s.get('passes')!=2:raise ValueError('Resumen inválido.')
    if any(s.get(k) is not False for k in ('trading_backtest','market_run_enabled','costs_verified')):raise ValueError('Fuera de alcance.')
    r=s['results']
    if 'predictions' in r or r['search_candidates']!=18 or r['fits_per_pass']!=54 or sum(len(c['trials']) for c in r['selections'])!=18 or r['winner_promoted'] is not False or r['historically_pristine_holdout'] is not False:raise ValueError('Presupuesto/alcance distintos.')
    text=canonical(s)
    if len(text.encode())>60000:raise ValueError('No truncar datos.')
    return {'name':CHECK_NAME,'head_sha':sha,'status':'completed','conclusion':'success','output':{'title':'Controlled convergence study completed, no trading approval','summary':'Same source/target/features; SGD control reproduced, solver convergence checked; 18 inner-only candidates; all external outcomes reported.','text':'```json\n'+text+'\n```'}}


def main():
    s=json.loads(Path('data/converged_classifier_run/summary.json').read_text());repo=os.environ['GITHUB_REPOSITORY']
    r=subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],input=canonical(payload(s,os.environ['GITHUB_SHA'])),text=True,capture_output=True,check=True)
    c=json.loads(r.stdout);print(json.dumps({'id':c['id'],'url':c['html_url']}))


if __name__=='__main__':main()
