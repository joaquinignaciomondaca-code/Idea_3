"""Audita datos de entrenamiento de fits ya registrados; no puntúa externos."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
import scipy
from microtrade.feature_study import NAMES,BASELINE,prepare,fit_scaler,transform
from microtrade.numerical_audit import audit_case
from microtrade.online import canonical
from scripts.audit_primary_bundle import audit_bundle
from scripts.run_primary_predictive import validate_artifact
from scripts.run_feature_study import load_extended


def run(package,metadata,previous,prior_metadata,spec,output):
    if np.__version__!='2.2.6' or scipy.__version__!='1.15.3':raise ValueError('Versiones incorrectas.')
    validate_artifact(metadata,spec['source']);validate_artifact(prior_metadata,spec['prior_artifact'])
    old_spec=json.loads(Path('experiments/feature_ablation.json').read_text())
    old_summary=json.loads(Path('artifacts/feature_ablation/summary.json').read_text())
    if hashlib.sha256(canonical(old_spec).encode()).hexdigest()!=spec['feature_spec_sha256']:raise ValueError('Protocolo previo alterado.')
    files=list(previous.rglob('full_result_1.json'))
    if len(files)!=1:raise ValueError('Registros previos ausentes o ambiguos.')
    old=json.loads(files[0].read_text())
    if hashlib.sha256(canonical(old).encode()).hexdigest()!=old_summary['full_result_sha256']:raise ValueError('Registro previo alterado.')
    directory=package/'data/primary_import';plan=json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'],plan['end']]!=old_spec['data_window']:raise ValueError('Ventana distinta.')
    source_audit=audit_bundle(directory,plan,compare_mirror=False)
    if source_audit['status']!='CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':raise ValueError('Fuente no supera reauditoría.')
    if any(not (directory/name).is_file() for name in ('BINANCE_TERMS.md','ATTRIBUTION.txt')):raise ValueError('Falta atribución/términos.')
    rows=load_extended(directory,plan)
    if hashlib.sha256(canonical([vars(r) for r in rows]).encode()).hexdigest()!=old_summary['extended_data_sha256']:raise ValueError('Datos distintos del experimento auditado.')
    data=prepare(rows);index={d:i for i,d in enumerate(data['dates'])};cases=[]
    for block in old_spec['outer_blocks']:
        for name,names in (('baseline3',BASELINE),('all24',NAMES)):
            original=next(f for f in old['outer_fit_audit'] if f['block']==block['name'] and f['model']=='fixed/'+name)
            adaptive=next(f for f in old['outer_fit_audit'] if f['block']==block['name'] and f['model']=='adaptive/'+name)
            if original['weights']!=adaptive['weights']:raise ValueError('Estados iniciales fijo/adaptativo diferentes.')
            cases.append((block['name']+'/'+name,index[block['test'][0]]-2,names,original))
    cases.append(('first_inner_2022/all24',index[old_spec['outer_blocks'][0]['inner'][0][0]]-2,NAMES,None))
    results=[]
    for name,cutoff,names,original in cases:
        eligible=np.arange(90,cutoff-1)[-old_spec['training_window']:]
        raw=data['x'][:,[NAMES.index(n) for n in names]]
        center,scale=fit_scaler(raw[eligible]);x=transform(raw[eligible],center,scale);y=data['y'][eligible+2]
        if original and (original['cutoff']!=data['dates'][cutoff] or original['training_rows']!=len(y) or not np.allclose(center,original['center'],atol=1e-12,rtol=1e-12) or not np.allclose(scale,original['scale'],atol=1e-12,rtol=1e-12)):
            raise ValueError('No reconstruye entrenamiento/escala del registro anterior.')
        result=audit_case(x,y,old_spec,original['weights'] if original else None)
        results.append({'name':name,'cutoff':data['dates'][cutoff],'last_training_label':data['dates'][int(eligible[-1])+2],**result})
    if len(results)!=spec['case_count']:raise ValueError('Presupuesto incorrecto.')
    summary={'experiment_id':spec['id'],'spec_sha256':hashlib.sha256(canonical(spec).encode()).hexdigest(),
             'source':spec['source'],'prior_artifact':spec['prior_artifact'],'data_rows':len(rows),
             'source_audit':{k:source_audit[k] for k in ('valid_archives','expected_rows','observed_rows','errors','missing_dates','extra_dates')},
             'cases':results,'training_only':True,'trading_backtest':False,'market_run_enabled':False,
             'external_scores_recomputed':False,'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
             'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('microtrade/numerical_audit.py','microtrade/feature_study.py','scripts/run_numerical_audit.py')}}
    output.mkdir(parents=True,exist_ok=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cases':len(results),'epochs10_converged':[r['epochs10_converged_at_gradient_1e7'] for r in results]},indent=2))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','metadata','previous','prior-metadata'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/numerical_audit_run'));a=p.parse_args()
    run(a.package,json.loads(a.metadata.read_text()),a.previous,json.loads(a.prior_metadata.read_text()),json.loads(Path('experiments/numerical_audit.json').read_text()),a.output)


if __name__=='__main__':main()
