"""Publica la auditoría numérica train-only, sin certificar rendimiento financiero."""
import json
import os
import subprocess
from pathlib import Path
from microtrade.online import canonical

CHECK_NAME='Numerical audit — training objective'


def payload(s,sha):
    allowed={'experiment_id','spec_sha256','source','prior_artifact','data_rows','source_audit','cases','training_only','trading_backtest','market_run_enabled','external_scores_recomputed','environment','code_sha256'}
    if set(s)-allowed or s.get('experiment_id')!='NUMERICAL-AUDIT-001' or s.get('training_only') is not True or len(s.get('cases',[]))!=7:
        raise ValueError('Resumen no autorizado.')
    if any(s.get(k) is not False for k in ('trading_backtest','market_run_enabled','external_scores_recomputed')):raise ValueError('Fuera del alcance.')
    text=canonical(s)
    if len(text.encode())>60000:raise ValueError('No truncar auditoría.')
    return {'name':CHECK_NAME,'head_sha':sha,'status':'completed','conclusion':'success','output':{
        'title':'Numerical checks completed, not model profitability approval',
        'summary':'Seven train-only cases; two independent solvers, finite differences and original recorded fits. Nonconvergence at ten epochs is reported, not suppressed.',
        'text':'```json\n'+text+'\n```'}}


WEEKLY_CHECK_NAME='Weekly return adaptation — aggregate report'


def weekly_payload(s,sha):
    allowed={'experiment_id','source','spec_sha256','data_rows','extended_data_sha256','source_audit','results','reproduced','passes','trading_backtest','market_run_enabled','costs_verified','environment','full_result_sha256','code_sha256'}
    if set(s)-allowed or s.get('experiment_id')!='WEEKLY-RETURN-ADAPTATION-001' or s.get('reproduced') is not True or s.get('passes')!=2:
        raise ValueError('Resumen semanal no autorizado.')
    if any(s.get(k) is not False for k in ('trading_backtest','market_run_enabled','costs_verified')):raise ValueError('Fuera del alcance.')
    r=s['results']
    if 'predictions' in r or r['model_fits_per_pass']!=6 or r['winner_promoted'] is not False or r['historically_pristine_holdout'] is not False:
        raise ValueError('Presupuesto o alcance diferentes.')
    text=canonical(s)
    if len(text.encode())>60000:raise ValueError('No truncar resultados.')
    return {'name':WEEKLY_CHECK_NAME,'head_sha':sha,'status':'completed','conclusion':'success','output':{
        'title':'Weekly adaptation completed; no trading approval',
        'summary':'Partial weekly momentum adaptation, not exact paper replication; all models/cohorts and both exploratory bootstrap lengths reported.',
        'text':'```json\n'+text+'\n```'}}


def main():
    repo=os.environ['GITHUB_REPOSITORY'];sha=os.environ['GITHUB_SHA']
    for path,builder in (('data/numerical_audit_run/summary.json',payload),('data/weekly_adaptation_run/summary.json',weekly_payload)):
        s=json.loads(Path(path).read_text())
        r=subprocess.run(['gh','api','--method','POST',f'repos/{repo}/check-runs','--input','-'],input=canonical(builder(s,sha)),text=True,capture_output=True,check=True)
        c=json.loads(r.stdout);print(json.dumps({'id':c['id'],'url':c['html_url']}))


if __name__=='__main__':main()
