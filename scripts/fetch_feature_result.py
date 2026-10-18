"""Recupera resultados existentes de ablación por Checks API; nunca inicia cómputo."""
import argparse
import hashlib
import json
import math
from datetime import date,timedelta
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import api,REPO
from scripts.publish_feature_check import CHECK_NAME,payload

REVISION='02a5f9c696f299cdf9e101f0ef25b54c6b80c3fc'
RUN_ID=39082812342


def validate_result(check,run,spec,revision):
    if run.get('head_sha')!=revision or run.get('conclusion')!='success' or run.get('path')!='.github/workflows/feature-ablation.yml':
        raise ValueError('Workflow/revisión/estado diferentes.')
    if check.get('head_sha')!=revision or check.get('name')!=CHECK_NAME or check.get('conclusion')!='success' or check.get('app',{}).get('slug')!='github-actions':
        raise ValueError('Productor/revisión/Check diferentes.')
    text=check['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):
        raise ValueError('Formato incorrecto.')
    s=json.loads(text[8:-4]); payload(s,revision)
    if s['source']!=spec['source'] or s['spec_sha256']!=hashlib.sha256(canonical(spec).encode()).hexdigest():
        raise ValueError('Protocolo/fuente distintos.')
    names=sum(spec['features'].values(),[]); groups=set(spec['features'])
    pairs={(b['name'],m) for b in spec['outer_blocks'] for m in ('fixed','adaptive')}
    if len(s['selections'])!=len(pairs) or {(c['block'],c['mode']) for c in s['selections']}!=pairs:
        raise ValueError('Selecciones incompletas.')
    for c in s['selections']:
        block=next(b for b in spec['outer_blocks'] if b['name']==c['block'])
        expected_cutoff=(date.fromisoformat(block['test'][0])-timedelta(days=2)).isoformat()
        if c['selection_data_end']!=expected_cutoff:
            raise ValueError('Selección no causal.')
        n=[(date.fromisoformat(b)-date.fromisoformat(a)).days+1 for a,b in block['inner']]
        if c['inner_fold_n']!=n or {r['name'] for r in c['feature_importance']}!=set(names) or {r['name'] for r in c['family_importance']}!=groups:
            raise ValueError('Ablaciones o cobertura interna alteradas.')
        for r in c['feature_importance']+c['family_importance']:
            ds=r['delta_by_fold']; delta=sum(v*w for v,w in zip(ds,n))/sum(n)
            if len(ds)!=2 or not math.isfinite(r['delta_log_loss']) or not math.isclose(delta,r['delta_log_loss'],abs_tol=1e-12):
                raise ValueError('Importancia no coincide con folds.')
            if r['positive_both_folds']!=all(v>0 for v in ds):
                raise ValueError('Regla de estabilidad alterada.')
        ranking=sorted(c['feature_importance'],key=lambda r:(-r['delta_log_loss'],r['name']))
        selected=[r['name'] for r in ranking if r['positive_both_folds']][:spec['max_selected_features']]
        if c['selected_features']!=selected:
            raise ValueError('Regla de selección alterada.')
    expected={m+'/'+n for m in ('fixed','adaptive') for n in spec['outer_models']}|{'constant_p0_5','persistence'}
    if set(s['pooled'])!=expected or len(s['blocks'])!=3:
        raise ValueError('Modelos/períodos omitidos.')
    for b,planned in zip(s['blocks'],spec['outer_blocks']):
        count=(date.fromisoformat(planned['test'][1])-date.fromisoformat(planned['test'][0])).days+1
        if b['name']!=planned['name'] or b['test']!=planned['test'] or set(b['metrics'])!=expected or any(r['n']!=count for r in b['metrics'].values()):
            raise ValueError('Cobertura externa diferente.')
    for key,r in s['pooled'].items():
        count=sum(b['metrics'][key]['n'] for b in s['blocks'])
        if r['n']!=count:
            raise ValueError('Cobertura agregada diferente.')
        for metric in ('log_loss','brier','accuracy'):
            expected_value=sum(b['metrics'][key]['n']*b['metrics'][key][metric] for b in s['blocks'])/count
            if not math.isclose(r[metric],expected_value,abs_tol=1e-12):
                raise ValueError('Agregación no ponderada por observaciones.')
    return s


def render(s,url):
    labels={'trend':'Tendencia','volatility':'Volatilidad','activity':'Actividad','candles':'Forma de velas'}
    lines=['# ¿Qué variables aportaron a la predicción?', '', '**FEATURE-ABLATION-001 — experimento ejecutado, solo investigación predictiva retrospectiva.**', '',
           f'Ejecución: {url}', '', '## Qué se probó', '',
           '- 24 variables: seis de tendencia, seis de volatilidad, seis de actividad y seis de forma de las velas. Originales oficiales Binance BTCUSDT, no un espejo.',
           '- Ablación con reentrenamiento: quitar una variable/familia y volver a ajustar. Importancia = log-loss SIN esa información − log-loss CON las24. Positivo: quitarla perjudicó; negativo: quitarla ayudó. No es porcentaje ni causalidad.',
           '- Rankings individuales calculados SOLO en dos validaciones internas por bloque; se seleccionan hasta seis variables con delta positivo en ambos folds. Cada selección se congela antes de probar el bloque externo. Si ninguna cumple, solo intercepto.',
           '- Tres bloques externos: 2023, 2024, 2025–26-09-2026. Misma receta para todos: logística SGD fija/adaptativa, tasa0.001, L2=0.01, diez épocas, ventana365, warmup90, scaler mediana/IQR exclusivamente de entrenamiento y clipping[-5,5]. No se optimizaron estos hiperparámetros.',
           '- 390 fits prescritos por pasada, dos pasadas idénticas: 780 fits en total, sin HPO ni elección de semilla. No se trata del presupuesto de 30 trials del estudio anterior.', '',
           '## Prueba externa: ¿más variables ayudaron?', '',
           'Menor log-loss/Brier es mejor. Todos tienen 1.365 etiquetas. Comparar baseline3 con all24 dentro de ESTA receta; no mezclar con scores de protocolos anteriores.', '',
           '| Modelo | Log-loss ↓ | Brier ↓ | Acierto |','|---|---:|---:|---:|']
    for key in ('constant_p0_5','persistence','fixed/baseline3','fixed/all24','fixed/selected_inner','adaptive/baseline3','adaptive/all24','adaptive/selected_inner'):
        r=s['pooled'][key]; lines.append(f"| {key} | {r['log_loss']:.6f} | {r['brier']:.6f} | {r['accuracy']*100:.2f}% |")
    lines += ['', '### Lectura del resultado', '']
    if all(s['pooled'][m+'/all24']['log_loss'] > s['pooled'][m+'/baseline3']['log_loss'] for m in ('fixed','adaptive')):
        lines.append('- **Añadir las24 empeoró el log-loss agregado frente a tres señales**, tanto en fijo como adaptativo.')
    if all(s['pooled'][m+'/selected_inner']['log_loss'] < s['pooled'][m+'/all24']['log_loss'] for m in ('fixed','adaptive')):
        lines.append('- La selección interna redujo el deterioro respecto de usarlo todo. Eso no demuestra que el subconjunto sea mejor que baseline3 ni que p=0.5.')
    if all(r['log_loss'] >= s['pooled']['constant_p0_5']['log_loss'] for r in s['pooled'].values()):
        lines.append('- **Ningún modelo aprendido superó p=0.5 en log-loss agregado**. No se ha demostrado señal predictiva útil con esta receta.')
    empty=[c['block']+'/'+c['mode'] for c in s['selections'] if not c['selected_features']]
    if empty:
        lines.append('- Ninguna variable cumplió el requisito en ambos folds en: '+', '.join(empty)+'. Se usó solo intercepto; no se forzaron seis variables ni se ocultó el resultado.')
    lines+=['', '## Importancia individual en validaciones internas', '',
            'Ranking descriptivo por modo: deltas ponderados por observaciones de sus tres validaciones dobles. «Estable» cuenta bloques donde quitarla perjudicó en ambos folds (máximo3). '
            'No son tres réplicas independientes ni un ranking universal; las listas globales NO se usaron para reentrenar después de ver externos. Se muestran las24, incluidos los deltas negativos.', '']
    for mode in ('fixed','adaptive'):
        choices=[c for c in s['selections'] if c['mode']==mode]; scores=[]
        for name in [r['name'] for r in choices[0]['feature_importance']]:
            vals=[(next(r for r in c['feature_importance'] if r['name']==name),sum(c['inner_fold_n'])) for c in choices]
            value=sum(r['delta_log_loss']*n for r,n in vals)/sum(n for _,n in vals)
            scores.append((name,value,sum(r['positive_both_folds'] for r,_ in vals)))
        lines += [f'### {mode}', '', '| Variable | Δ log-loss interno | Estable /3 |','|---|---:|---:|']
        for name,value,stable in sorted(scores,key=lambda v:(-v[1],v[0])):
            lines.append(f'| {name} | {value:+.6f} | {stable} |')
    lines+=['', '## Subconjuntos elegidos antes de cada test', '', '| Bloque | Modo | Variables |','|---|---|---|']
    for c in s['selections']:
        lines.append(f"| {c['block']} | {c['mode']} | {', '.join(c['selected_features']) or 'Solo intercepto'} |")
    lines+=['', '## Ablaciones familiares externas: diagnóstico, no selección', '',
            'Diferencia de log-loss agregado respecto de all24, con reentrenamiento en ambos casos. Positivo favorece conservar la familia; negativo favorece eliminarla en esta receta y período. Estos resultados NO alimentan el selector.', '',
            '| Familia eliminada | Δ fijo | Δ adaptativo |','|---|---:|---:|']
    for group in labels:
        ds=[s['pooled'][m+'/without_'+group]['log_loss']-s['pooled'][m+'/all24']['log_loss'] for m in ('fixed','adaptive')]
        lines.append(f'| {labels[group]} | {ds[0]:+.6f} | {ds[1]:+.6f} |')
    lines+=['', '## Todos los resultados externos por bloque', '', '| Bloque | Modelo | n | Log-loss ↓ | Brier ↓ |','|---|---|---:|---:|---:|']
    for b in s['blocks']:
        for key,r in b['metrics'].items():
            lines.append(f"| {b['name']} | {key} | {r['n']} | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines+=['', '## Límites y trazabilidad', '',
            '- Un ranking de un modelo débil no identifica automáticamente una señal útil. Las variables correlacionadas pueden sustituirse y los efectos individuales no se suman.',
            '- El histórico BTC ya estaba inspeccionado. Externo significa excluido del selector de ese bloque, no holdout virgen ni publicación prospectiva. Sin pruebas de significancia ni disponibilidad histórica certificada.',
            '- No se promueve un ganador, se cambia la selección ni se amplía la búsqueda después de ver los resultados. El estado success del workflow solo confirma ejecución y validaciones.',
            '- No se calcularon rentabilidad de USD20, Sharpe ni costos operativos. Actividad/iliquidez son proxies de velas, no spread ejecutable. No Laya, evolución ni trading real.',
            f"- Reauditoría: {s['source_audit']['valid_archives']} archivos, {s['data_rows']} días; quote volume, trades y taker validados adicionalmente. Dos pasadas iguales en rankings, selecciones, escalas, pesos iniciales y predicciones. Python {s['environment']['python']}, NumPy {s['environment']['numpy']}.",
            '- summary.json conserva las24 ablaciones individuales y cuatro familiares de cada modo/bloque y todos los scores externos. Los registros completos, escalas, pesos y pronósticos están en el artifact del workflow, retención7días. Agregados preservados en Git.', '',
            '## Fuentes, licencia y reproducción', '',
            'Binance Vision: https://data.binance.vision/ . Formato oficial Klines: https://github.com/binance/binance-public-data/tree/d571690eb66760763b0bd6e27e8cd35603c7e244 . '
            'Términos CC BY-NC-SA4.0 salvo designación distinta; solo investigación no comercial. Informe derivado bajo CC BY-NC-SA4.0. Términos/atribución en el artifact; sin aval del proveedor.', '',
            'Protocolo: experiments/feature_ablation.json. Fórmulas y limitaciones: docs/investigacion/14_variables_y_ablacion.md.', '',
            '```bash','python -m scripts.fetch_feature_result','```', '',
            'Solo recupera agregados existentes mediante Checks API; no inicia nuevos fits ni requiere descargar artifact storage.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--revision',default=REVISION); p.add_argument('--run-id',type=int,default=RUN_ID); a=p.parse_args()
    spec=json.loads(Path('experiments/feature_ablation.json').read_text()); run=api(f'repos/{REPO}/actions/runs/{a.run_id}')
    checks=api(f'repos/{REPO}/commits/{a.revision}/check-runs?per_page=100')['check_runs']
    matches=[c for c in checks if c['name']==CHECK_NAME]
    if len(matches)!=1:raise ValueError('Check ausente o ambiguo.')
    c=matches[0]; s=validate_result(c,run,spec,a.revision)
    out=Path('artifacts/feature_ablation'); out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
    receipt={k:c[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')}
    receipt.update({'run_id':run['id'],'run_url':run['html_url'],'app':c['app']['slug'], 'summary_sha256':hashlib.sha256(canonical(s).encode()).hexdigest()})
    (out/'check_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (out/'informe.md').write_text(render(s,run['html_url']))
    print(json.dumps({'report':str(out/'informe.md'),'reproduced':s['reproduced'],'pooled':s['pooled']},indent=2))


if __name__=='__main__':main()
