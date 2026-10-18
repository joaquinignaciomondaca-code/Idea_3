"""Recupera estudio convergido existente por Checks API, sin nuevos fits."""
import argparse
import hashlib
import json
import math
from datetime import date,timedelta
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import api,REPO
from scripts.publish_converged_check import CHECK_NAME,payload
REVISION='71cacc7746c55b439e3826233997a6ba577eef09'
RUN_ID=39084945583


def validate(check,run,spec,revision):
    if run.get('head_sha')!=revision or run.get('conclusion')!='success' or run.get('path')!='.github/workflows/converged-classifier.yml':raise ValueError('Workflow/revisión incorrectos.')
    if check.get('head_sha')!=revision or check.get('name')!=CHECK_NAME or check.get('conclusion')!='success' or check.get('app',{}).get('slug')!='github-actions':raise ValueError('Check/productor incorrectos.')
    text=check['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):raise ValueError('Formato incorrecto.')
    s=json.loads(text[8:-4]);payload(s,revision)
    if s['source']!=spec['source'] or s['spec_sha256']!=hashlib.sha256(canonical(spec).encode()).hexdigest():raise ValueError('Fuente/protocolo distintos.')
    if s['data_rows']!=1730 or s['source_audit']['valid_archives']!=82 or any(s['source_audit'][k] for k in ('errors','missing_dates','extra_dates')):raise ValueError('Fuente incompleta.')
    r=s['results'];pairs={(b['name'],f) for b in spec['outer_blocks'] for f in ('baseline3','all24')}
    if len(r['selections'])!=6 or {(c['block'],c['features']) for c in r['selections']}!=pairs or len(r['fit_audit'])!=18:raise ValueError('Faltan selecciones/fits.')
    for c in r['selections']:
        if [t['alpha'] for t in c['trials']]!=spec['alphas']:raise ValueError('Candidatos omitidos.')
        for t in c['trials']:
            value=sum(n*v for n,v in zip(t['fold_n'],t['fold_losses']))/sum(t['fold_n'])
            if len(t['fold_n'])!=2 or not math.isclose(value,t['value'],abs_tol=1e-12):raise ValueError('Objetivo interno alterado.')
        if c['alpha']!=min(c['trials'],key=lambda t:(t['value'],t['alpha']))['alpha']:raise ValueError('Selección distinta.')
        block=next(b for b in spec['outer_blocks'] if b['name']==c['block'])
        if c['selection_data_end']!=(date.fromisoformat(block['test'][0])-timedelta(days=2)).isoformat():raise ValueError('Selección futura.')
    expected_fits={(b['name'],f+'/'+m) for b in spec['outer_blocks'] for f in ('baseline3','all24') for m in ('sgd10','converged_same_alpha','converged_selected')}
    if {(f['block'],f['model']) for f in r['fit_audit']}!=expected_fits:raise ValueError('Fits duplicados/omitidos.')
    for f in r['fit_audit']:
        if f['last_training_label']>f['cutoff']:raise ValueError('Fit con futuro.')
        if not f['model'].endswith('/sgd10') and (f['gradient_inf']>1e-7 or f['scipy_weight_max_difference']>1e-4):raise ValueError('Convergencia/solvers no verificados.')
    models={f+'/'+m for f in ('baseline3','all24') for m in ('sgd10','converged_same_alpha','converged_selected')}|{'constant_p0_5','historical_prior','persistence'}
    if set(r['pooled'])!=models or len(r['blocks'])!=3:raise ValueError('Modelos/bloques omitidos.')
    for name,v in r['pooled'].items():
        n=sum(b['metrics'][name]['n'] for b in r['blocks'])
        if v['n']!=n or n!=1365:raise ValueError('Cobertura distinta.')
        for metric in ('log_loss','brier','accuracy'):
            expected=sum(b['metrics'][name]['n']*b['metrics'][name][metric] for b in r['blocks'])/n
            if not math.isclose(v[metric],expected,abs_tol=1e-12):raise ValueError('Agregación no ponderada.')
    if set(r['paired_loss_ci'])!={'baseline3/converged_selected','all24/converged_selected'}:raise ValueError('Comparaciones omitidas.')
    for name,refs in r['paired_loss_ci'].items():
        if set(refs)!={'constant_p0_5','historical_prior',name.split('/')[0]+'/sgd10'}:raise ValueError('Referencias omitidas.')
        for reference,intervals in refs.items():
            if set(intervals)!={'14','60'}:raise ValueError('Intervalos omitidos.')
            for ci in intervals.values():
                if ci['lower_95']>ci['upper_95'] or not math.isclose(ci['mean_difference'],r['pooled'][name]['log_loss']-r['pooled'][reference]['log_loss'],abs_tol=1e-12):raise ValueError('Diferencia/intervalo alterados.')
    return s


def render(s,url):
    r=s['results'];p=r['pooled'];lines=['# Clasificador con convergencia controlada — resultados', '',f'Ejecución: {url}', '',
        '**Comparación retrospectiva controlada. No trading, PnL ni holdout históricamente virgen.**', '',
        '## Diseño', '',
        '- Mismos originales BTCUSDT, etiqueta close[i+2]>open[i+2], conjuntos baseline3/all24 y ventanas que FEATURE-ABLATION-001. Warmup90, train365 maduro, escala mediana/IQR de train y clipping[-5,5]. Modelos fijos, sin updates adaptativos.',
        '- SGD10 lr0.001/L2=0.01 reproduce los controles anteriores dentro de1e-12. Batch con MISMA L2=0.01 aísla el efecto de convergencia. Batch seleccionado cambia solamente L2 con validación interna.',
        '- Objetivo batch: log-loss medio+alpha/2*sum(pesos sin intercepto²). Newton/Armijo tolerancia gradiente1e-8, máximo100iteraciones; cada ajuste externo batch verificado con SciPy independiente.',
        '- Grid L2=0.001/0.01/0.1:18 candidatos en seis estudios (dos matrices×tres bloques),36 fits internos+18externos por pasada. Dos pasadas idénticas=108fits, más24 verificaciones SciPy; no búsqueda de épocas, horizonte, semillas ni umbrales.',
        '- Prior histórico suavizado: (subidas+1)/(n+2) SOLO sobre las mismas etiquetas maduras del train. También p=0.5 y persistencia0.55/0.45.', '',
        '## Todos los resultados agregados externos', '', 'Cada predictor tiene1.365 etiquetas, 2023–26-09-2026. Menor log-loss/Brier es mejor.', '',
        '| Predictor | Log-loss ↓ | Brier ↓ | Acierto |','|---|---:|---:|---:|']
    for name in ('constant_p0_5','historical_prior','persistence',*[f+'/'+m for f in ('baseline3','all24') for m in ('sgd10','converged_same_alpha','converged_selected')]):
        v=p[name];lines.append(f"| {name} | {v['log_loss']:.6f} | {v['brier']:.6f} | {v['accuracy']*100:.2f}% |")
    lines+=['', '## Efecto aislado del optimizador', '']
    for f in ('baseline3','all24'):
        a,b=p[f+'/sgd10']['log_loss'],p[f+'/converged_same_alpha']['log_loss']
        lines.append(f'- {f}: SGD10 {a:.6f} → batch misma L2 {b:.6f}; cambio {b-a:+.6f} (positivo=peor).')
    if all(p[f+'/converged_same_alpha']['log_loss']>p[f+'/sgd10']['log_loss'] for f in ('baseline3','all24')):
        lines.append('**Converger mejor el objetivo de train empeoró el score externo en ambos conjuntos con la misma L2.** La falta de convergencia no era evidencia de que resolver mejor train fuera a mejorar test; early stopping podía regularizar implícitamente.')
    if all(p[f+'/converged_selected']['log_loss']>=p['constant_p0_5']['log_loss'] for f in ('baseline3','all24')):
        lines.append('**Los dos procedimientos con L2 seleccionada internamente siguen sin superar p=0.5 en log-loss agregado.** No se ha demostrado señal útil; no se promueve ganador.')
    lines+=['', '## Parámetros elegidos sin usar test', '', '| Bloque | Features | L2 elegida |','|---|---|---:|']
    for c in r['selections']:lines.append(f"| {c['block']} | {c['features']} | {c['alpha']} |")
    lines+=['', 'Los18 candidatos completos y sus pérdidas por fold están en summary.json. No se amplía el grid después de ver parámetros o externos.', '',
        '## Gradientes finales de los ajustes externos', '', '| Bloque | Modelo | Gradiente infinito | Diferencia coef. vs SciPy |','|---|---|---:|---:|']
    for f in r['fit_audit']:
        if not f['model'].endswith('/sgd10'):lines.append(f"| {f['block']} | {f['model']} | {f['gradient_inf']:.3e} | {f['scipy_weight_max_difference']:.3e} |")
    lines+=['', '## Incertidumbre exploratoria', '',
        'Diferencias emparejadas de log-loss selected−referencia; negativo favorece selected. Bootstrap circular dentro de cada bloque externo,2000réplicas,seed1701, bloques14/60días, percentiles95%. Sin corrección por multiplicidad/investigación previa; no se elige modelo ni largo por este resultado.', '',
        '| Selected | Referencia | Bloque días | Δ medio | Inferior95% | Superior95% |','|---|---|---:|---:|---:|---:|']
    for name,refs in r['paired_loss_ci'].items():
        for ref,intervals in refs.items():
            for length in ('14','60'):
                ci=intervals[length];lines.append(f"| {name} | {ref} | {length} | {ci['mean_difference']:+.6f} | {ci['lower_95']:+.6f} | {ci['upper_95']:+.6f} |")
    lines+=['', '## Todos los bloques externos', '', '| Bloque | Modelo | n | Log-loss ↓ | Brier ↓ |','|---|---|---:|---:|---:|']
    for b in r['blocks']:
        for name,v in b['metrics'].items():lines.append(f"| {b['name']} | {name} | {v['n']} | {v['log_loss']:.6f} | {v['brier']:.6f} |")
    lines+=['', '## Alcance y trazabilidad', '',
        '- Se mantienen los resultados anteriores sin sobrescribirlos. El comparador SGD se recalcula para verificar la comparación controlada, no para sustituir el informe previo.',
        '- Todo BTC ya fue inspeccionado. Excluir test del selector no borra decisiones humanas previas. Los intervalos no certifican generalización ni disponibilidad histórica de datos.',
        '- No se atribuye causalidad general a un experimento: el efecto observado del optimizador es condicional a estos datos, etiqueta, scaler, L2 y ventana. Más optimización no fabrica información.',
        '- No se alteran métricas para encontrar un resultado favorable, se elige un ganador por externos ni se pasa a una política deUSD20 sin costos/filtros/fills comprobados. Sin Laya, evolución, órdenes ni inferencia pagada.',
        f"- Reauditoría82 originales/1730días, fuente y control SGD verificados. Python{s['environment']['python']}, NumPy{s['environment']['numpy']}, SciPy{s['environment']['scipy']}. Dos pasadas iguales en fits, candidatos, selecciones, predicciones, métricas e intervalos.",
        '- Resultados completos y pronósticos en artifact, retención7días; agregados, coeficientes/escalas y recibo se preservan en Git. Success significa controles/cálculo completados, no ventaja financiera.', '',
        'Protocolo: experiments/converged_classifier.json; documentación: docs/investigacion/17_clasificador_con_convergencia.md.', '',
        '```bash','python -m scripts.fetch_converged_result','```', '',
        'Recupera agregados existentes por Checks API, sin nuevos fits ni descargas manuales. Fuente Binance Vision https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial. Informe derivado bajo CC BY-NC-SA4.0; términos/atribución en el artifact, sin aval del proveedor.', '']
    return '\n'.join(lines)


def main():
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--revision',default=REVISION);q.add_argument('--run-id',type=int,default=RUN_ID);o=q.parse_args()
    run=api(f'repos/{REPO}/actions/runs/{o.run_id}');checks=api(f'repos/{REPO}/commits/{o.revision}/check-runs?per_page=100')['check_runs'];matches=[c for c in checks if c['name']==CHECK_NAME]
    if len(matches)!=1:raise ValueError('Check ausente o ambiguo.')
    c=matches[0];s=validate(c,run,json.loads(Path('experiments/converged_classifier.json').read_text()),o.revision)
    out=Path('artifacts/converged_classifier');out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(s,indent=2)+'\n');(out/'informe.md').write_text(render(s,run['html_url']))
    receipt={k:c[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')}
    receipt.update({'run_id':run['id'],'run_url':run['html_url'],'app':c['app']['slug'],'summary_sha256':hashlib.sha256(canonical(s).encode()).hexdigest()})
    (out/'check_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'report':str(out/'informe.md'),'pooled':s['results']['pooled']},indent=2))


if __name__=='__main__':main()
