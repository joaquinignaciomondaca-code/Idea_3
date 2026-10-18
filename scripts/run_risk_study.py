"""Reaudita originales y ejecuta diagnóstico de riesgo sin HPO ni trading."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
import numpy as np
from microtrade.online import canonical
from microtrade.risk_forecast import study
from scripts.run_feature_study import load_extended
from scripts.run_primary_predictive import validate_artifact
from scripts.audit_primary_bundle import audit_bundle
CHECK_NAME='Risk persistence — aggregate report'


def run(package,metadata,spec,output):
    if np.__version__!='2.2.6':raise ValueError('NumPy distinto.')
    validate_artifact(metadata,spec['source']);directory=package/'data/primary_import';plan=json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'],plan['end']]!=spec['data_window']:raise ValueError('Ventana distinta.')
    audit=audit_bundle(directory,plan,compare_mirror=False)
    if audit['status']!='CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':raise ValueError('Reauditoría fallida.')
    if any(not (directory/n).is_file() for n in ('BINANCE_TERMS.md','ATTRIBUTION.txt')):raise ValueError('Falta atribución/términos.')
    rows=load_extended(directory,plan);digest=hashlib.sha256(canonical([vars(r) for r in rows]).encode()).hexdigest()
    old=json.loads(Path('artifacts/feature_ablation/summary.json').read_text())
    if digest!=old['extended_data_sha256']:raise ValueError('Datos diferentes del histórico registrado.')
    a,b=study(rows,spec),study(rows,spec)
    if a!=b:raise ValueError('Repetición diferente.')
    output.mkdir(parents=True,exist_ok=False);(output/'full_result.json').write_text(canonical(a))
    s={'experiment_id':spec['id'],'source':spec['source'],'spec_sha256':hashlib.sha256(canonical(spec).encode()).hexdigest(),
       'data_rows':len(rows),'data_sha256':digest,'results':{k:v for k,v in a.items() if k!='records'},'reproduced':True,
       'trading_backtest':False,'market_run_enabled':False,'forward_started':False,'historically_pristine_holdout':False,
       'source_audit':{k:audit[k] for k in ('valid_archives','observed_rows','errors','missing_dates','extra_dates')},
       'environment':{'python':platform.python_version(),'numpy':np.__version__},
       'full_result_sha256':hashlib.sha256(canonical(a).encode()).hexdigest(),
       'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('microtrade/risk_forecast.py','scripts/run_risk_study.py')}}
    (output/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s['results']['metrics'],indent=2));return s


def payload(s,sha):
    allowed={'experiment_id','source','spec_sha256','data_rows','data_sha256','results','reproduced','trading_backtest','market_run_enabled','forward_started','historically_pristine_holdout','source_audit','environment','full_result_sha256','code_sha256'}
    if set(s)-allowed or s.get('experiment_id')!='RISK-PERSISTENCE-001' or s.get('reproduced') is not True:raise ValueError('Resumen incorrecto.')
    if any(s.get(k) is not False for k in ('trading_backtest','market_run_enabled','forward_started','historically_pristine_holdout')) or 'records' in s['results'] or s['results']['winner_promoted'] is not False:raise ValueError('Alcance incorrecto.')
    text=canonical(s)
    if len(text.encode())>60000:raise ValueError('No truncar resultados.')
    return {'name':CHECK_NAME,'head_sha':sha,'status':'completed','conclusion':'success','output':{'title':'Risk diagnostic complete, not trading approval','summary':'Five frozen risk forecasts, no HPO, two identical historical passes. Forward reservation not started.','text':'```json\n'+text+'\n```'}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path);p.add_argument('--metadata',type=Path);p.add_argument('--publish',action='store_true');a=p.parse_args()
    output=Path('data/risk_study_run')
    if a.publish:
        s=json.loads((output/'summary.json').read_text());repo=os.environ['GITHUB_REPOSITORY']
        r=subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],input=canonical(payload(s,os.environ['GITHUB_SHA'])),text=True,capture_output=True,check=True)
        c=json.loads(r.stdout);print(json.dumps({'id':c['id'],'url':c['html_url']}))
    else:
        if a.package is None or a.metadata is None:p.error('--package and --metadata required')
        run(a.package,json.loads(a.metadata.read_text()),json.loads(Path('experiments/risk_persistence.json').read_text()),output)


if __name__=='__main__':main()
