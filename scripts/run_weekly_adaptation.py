"""Ejecuta adaptación semanal congelada; separada de auditoría train-only."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
from microtrade.online import canonical
from microtrade.weekly_reference import run as replay
from scripts.run_feature_study import load_extended
from scripts.run_primary_predictive import validate_artifact
from scripts.audit_primary_bundle import audit_bundle


def run(package,metadata,spec,output):
    if np.__version__!='2.2.6':raise ValueError('NumPy fuera del protocolo.')
    validate_artifact(metadata,spec['source']);directory=package/'data/primary_import'
    plan=json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'],plan['end']]!=spec['data_window']:raise ValueError('Ventana distinta.')
    audit=audit_bundle(directory,plan,compare_mirror=False)
    if audit['status']!='CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':raise ValueError('Reauditoría fallida.')
    if any(not (directory/n).is_file() for n in ('BINANCE_TERMS.md','ATTRIBUTION.txt')):raise ValueError('Falta atribución/términos.')
    rows=load_extended(directory,plan);a=replay(rows,spec);b=replay(rows,spec)
    if a!=b:raise ValueError('Cambia fits, predicciones, métricas o intervalos al repetir.')
    output.mkdir(parents=True,exist_ok=False)
    (output/'full_result.json').write_text(canonical(a))
    summary={'experiment_id':spec['id'],'source':spec['source'],'spec_sha256':hashlib.sha256(canonical(spec).encode()).hexdigest(),
             'data_rows':len(rows),'extended_data_sha256':hashlib.sha256(canonical([vars(r) for r in rows]).encode()).hexdigest(),
             'source_audit':{k:audit[k] for k in ('valid_archives','expected_rows','observed_rows','errors','missing_dates','extra_dates')},
             'results':{k:v for k,v in a.items() if k!='predictions'},'reproduced':True,'passes':2,
             'trading_backtest':False,'market_run_enabled':False,'costs_verified':False,
             'environment':{'python':platform.python_version(),'numpy':np.__version__},
             'full_result_sha256':hashlib.sha256(canonical(a).encode()).hexdigest(),
             'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('microtrade/weekly_reference.py','scripts/run_weekly_adaptation.py','microtrade/feature_study.py')}}
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary['results']['pooled'],indent=2));return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/weekly_adaptation_run'));a=p.parse_args()
    run(a.package,json.loads(a.metadata.read_text()),json.loads(Path('experiments/weekly_return_adaptation.json').read_text()),a.output)


if __name__=='__main__':main()
