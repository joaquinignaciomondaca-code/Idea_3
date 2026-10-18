"""Reauditoría y comparación congelada de clasificadores convergidos."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import numpy as np
import scipy
from microtrade.converged_classifier import study
from microtrade.online import canonical
from scripts.run_feature_study import load_extended
from scripts.run_primary_predictive import validate_artifact
from scripts.audit_primary_bundle import audit_bundle


def run(package,metadata,spec,output):
    if np.__version__!='2.2.6' or scipy.__version__!='1.15.3':raise ValueError('Versiones distintas.')
    validate_artifact(metadata,spec['source']);directory=package/'data/primary_import'
    plan=json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'],plan['end']]!=spec['data_window']:raise ValueError('Ventana distinta.')
    audit=audit_bundle(directory,plan,compare_mirror=False)
    if audit['status']!='CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':raise ValueError('Reauditoría fallida.')
    if any(not (directory/n).is_file() for n in ('BINANCE_TERMS.md','ATTRIBUTION.txt')):raise ValueError('Faltan términos/atribución.')
    rows=load_extended(directory,plan);old=json.loads(Path('artifacts/feature_ablation/summary.json').read_text())
    digest=hashlib.sha256(canonical([vars(r) for r in rows]).encode()).hexdigest()
    if digest!=old['extended_data_sha256']:raise ValueError('Datos distintos del control anterior.')
    a=study(rows,spec);b=study(rows,spec)
    if a!=b:raise ValueError('Cambian fits, selecciones, predicciones o métricas al repetir.')
    for label in ('baseline3','all24'):
        for metric in ('log_loss','brier','accuracy'):
            if not math.isclose(a['pooled'][label+'/sgd10'][metric],old['pooled']['fixed/'+label][metric],abs_tol=1e-12,rel_tol=0):raise ValueError('SGD10 no reproduce el control original.')
    output.mkdir(parents=True,exist_ok=False);(output/'full_result.json').write_text(canonical(a))
    # Bins y predicciones completos en artifact; Check conserva todos los modelos/candidatos.
    result={k:v for k,v in a.items() if k!='predictions'}
    for group in (result['pooled'],*(bb['metrics'] for bb in result['blocks'])):
        for key,m in list(group.items()):group[key]={k:m[k] for k in ('n','log_loss','brier','accuracy')}
    summary={'experiment_id':spec['id'],'source':spec['source'],'spec_sha256':hashlib.sha256(canonical(spec).encode()).hexdigest(),
             'data_rows':len(rows),'extended_data_sha256':digest,'source_audit':{k:audit[k] for k in ('valid_archives','observed_rows','errors','missing_dates','extra_dates')},
             'results':result,'reproduced':True,'sgd_baseline_reproduced':True,'passes':2,'trading_backtest':False,'market_run_enabled':False,'costs_verified':False,
             'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
             'full_result_sha256':hashlib.sha256((output/'full_result.json').read_bytes()).hexdigest(),
             'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('microtrade/converged_classifier.py','microtrade/feature_study.py','microtrade/numerical_audit.py','scripts/run_converged_classifier.py')}}
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['pooled'],indent=2));return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/converged_classifier_run'));a=p.parse_args()
    run(a.package,json.loads(a.metadata.read_text()),json.loads(Path('experiments/converged_classifier.json').read_text()),a.output)


if __name__=='__main__':main()
