"""Reaudita originales OHLCV/actividad y ejecuta dos veces la ablación congelada."""
import argparse
import csv
import hashlib
import io
import json
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from microtrade.feature_study import Candle, prepare, study
from microtrade.online import canonical
from scripts.audit_primary_bundle import audit_bundle
from scripts.audit_primary_prices import read_archive
from scripts.run_primary_predictive import validate_artifact


def load_extended(directory,plan):
    rows = {}
    for entry in plan['entries']:
        path = directory/entry['name']; checked = read_archive(path)
        with zipfile.ZipFile(path) as z:
            raw_rows = csv.reader(io.StringIO(z.read(path.stem+'.csv').decode('utf-8-sig')))
            for row in raw_rows:
                stamp = int(row[0]); divisor = 1_000_000 if stamp>=10**15 else 1000
                day = datetime.fromtimestamp(stamp//divisor,timezone.utc).date().isoformat()
                if day in rows:
                    raise ValueError('Día duplicado.')
                values = [float(row[i]) for i in (1,2,3,4,5,7)]
                if any(values[i]!=float(checked['rows'][day][field]) for i,field in enumerate(('open','high','low','close','volume'))):
                    raise ValueError('OHLCV diferente de auditoría.')
                trades = int(row[8]); taker_base = float(row[9]); taker_quote = float(row[10])
                if not np.isfinite(taker_base) or not 0<=taker_base<=values[4]*(1+1e-10):
                    raise ValueError('Volumen taker base inválido.')
                rows[day] = Candle(day,*values,trades,taker_quote)
    result = [rows[d] for d in sorted(rows)]
    prepare(result)  # Extiende validación previa a quote volume, trades y taker quote.
    return result


def core_metrics(result):
    return {k:result[k] for k in ('n','log_loss','brier','accuracy')}


def run(package,metadata,spec,output):
    if np.__version__!='2.2.6':
        raise ValueError('NumPy fuera del preregistro.')
    validate_artifact(metadata,spec['source'])
    directory = package/'data/primary_import'; plan = json.loads((directory/'BTCUSDT_plan.json').read_text())
    if [plan['start'],plan['end']]!=spec['data_window'] or plan['symbol']!='BTCUSDT':
        raise ValueError('Plan incorrecto.')
    audit = audit_bundle(directory,plan,compare_mirror=False)
    if audit['status']!='CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW':
        raise ValueError('Reauditoría fallida.')
    if any(not (directory/name).is_file() for name in ('BINANCE_TERMS.md','ATTRIBUTION.txt')):
        raise ValueError('Términos/atribución ausentes.')
    rows = load_extended(directory,plan)
    if len(rows)!=audit['expected_rows']:
        raise ValueError('Cobertura extendida incorrecta.')
    output.mkdir(parents=True,exist_ok=False)
    results = []
    for attempt in (1,2):
        r = study(rows,spec); (output/f'full_result_{attempt}.json').write_text(canonical(r)); results.append(r)
    if results[0]!=results[1]:
        raise ValueError('La repetición cambia importancias, selección, fits o predicciones.')
    r = results[0]
    summary = {'experiment_id':spec['id'], 'spec_sha256':hashlib.sha256(canonical(spec).encode()).hexdigest(),
               'source':spec['source'],'data_rows':len(rows),'extended_data_sha256':hashlib.sha256(canonical([vars(row) for row in rows]).encode()).hexdigest(),
               'source_audit':{k:audit[k] for k in ('expected_archives','valid_archives','expected_rows','observed_rows','errors','missing_dates','extra_dates')},
               'reproduced':True,'trading_backtest':False,'costs_verified':False,'market_run_enabled':False,
               'historically_pristine_holdout':False,'winner_promoted':False,'fits_per_pass':r['fits_per_pass'],'passes':2,'hpo_trials':0,
               'environment':{'python':platform.python_version(),'numpy':np.__version__},
               'selections':r['selections'], 'pooled':{k:core_metrics(v) for k,v in r['pooled'].items()},
               'blocks':[{'name':b['name'],'test':b['test'],'metrics':{k:core_metrics(v) for k,v in b['metrics'].items()}} for b in r['blocks']],
               'full_result_sha256':hashlib.sha256(canonical(r).encode()).hexdigest(),
               'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('microtrade/feature_study.py','scripts/run_feature_study.py','microtrade/online.py')},
               'license':spec['source']['license']}
    if len(canonical(summary).encode())>60000:
        raise ValueError('Resumen demasiado grande: no truncar candidatos.')
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    (output/'source_audit.json').write_text(json.dumps(audit,indent=2))
    (output/'spec.json').write_text(canonical(spec))
    print(json.dumps({'fits_per_pass':r['fits_per_pass'],'reproduced':True,'pooled':summary['pooled']},indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,required=True); p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/feature_study_run')); a=p.parse_args()
    run(a.package,json.loads(a.metadata.read_text()),json.loads(Path('experiments/feature_ablation.json').read_text()),a.output)


if __name__=='__main__':
    main()
