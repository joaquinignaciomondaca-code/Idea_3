"""Recupera auditoría y adaptación ya ejecutadas, sin iniciar más cálculos."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import api,REPO
from scripts.publish_numerical_check import CHECK_NAME,WEEKLY_CHECK_NAME,payload,weekly_payload

REVISION='049027a6c8a977645f9a6205173086145ce7013e'
RUN_ID=39083857802


def decode(check,run,spec,revision,name):
    if run.get('head_sha')!=revision or run.get('conclusion')!='success' or run.get('path')!='.github/workflows/numerical-audit.yml':raise ValueError('Workflow/revisión distintos.')
    if check.get('name')!=name or check.get('head_sha')!=revision or check.get('conclusion')!='success' or check.get('app',{}).get('slug')!='github-actions':raise ValueError('Productor/Check incorrectos.')
    text=check['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):raise ValueError('Formato incorrecto.')
    s=json.loads(text[8:-4])
    if s.get('experiment_id')!=spec['id'] or s.get('source')!=spec['source'] or s.get('spec_sha256')!=hashlib.sha256(canonical(spec).encode()).hexdigest():raise ValueError('Protocolo/fuente distintos.')
    audit=s['source_audit']
    if s['data_rows']!=1730 or audit['valid_archives']!=82 or any(audit[k] for k in ('errors','missing_dates','extra_dates')):raise ValueError('Reauditoría/cobertura incompleta.')
    return s


def validate_audit(check,run,spec,revision):
    s=decode(check,run,spec,revision,CHECK_NAME);payload(s,revision)
    if s['prior_artifact']!=spec['prior_artifact']:raise ValueError('Registros anteriores distintos.')
    t=spec['tolerances'];recorded=0
    for c in s['cases']:
        if c['last_training_label']>c['cutoff'] or [p['epochs'] for p in c['trajectory']]!=[0,1,10,100,1000]:raise ValueError('Cronología/presupuesto incorrectos.')
        for key,limit in (('gradient_fd_max_error',t['finite_difference']),('production_step_max_error',t['production_step']),('solver_max_weight_difference',t['weight_agreement']),('solver_max_probability_difference',t['probability_agreement']),('scipy_gradient_inf',t['scipy_gradient_inf'])):
            if not math.isfinite(c[key]) or c[key]>limit:raise ValueError('Control numérico no superado.')
        if not c['scipy_success'] or abs(c['newton_objective']-c['scipy_objective'])>t['objective_agreement'] or c['maximum_abs_logit']>=35 or c['hessian_min_eigenvalue']<=0:raise ValueError('Solvers/Hessiano/clipping inválidos.')
        if c['recorded_weight_max_error'] is not None:
            recorded+=1
            if c['recorded_weight_max_error']>t['recorded_weights']:raise ValueError('No reconstruye pesos anteriores.')
        if c['epochs10_converged_at_gradient_1e7']!=(c['trajectory'][2]['gradient_inf']<=1e-7):raise ValueError('Diagnóstico de convergencia alterado.')
        for p in c['trajectory']:
            if not math.isclose(p['objective']-c['newton_objective'],p['gap_to_optimum'],abs_tol=1e-12):raise ValueError('Gap incorrecto.')
    if recorded!=6:raise ValueError('Faltan estados previos auditados.')
    return s


def validate_weekly(check,run,spec,revision):
    s=decode(check,run,spec,revision,WEEKLY_CHECK_NAME);weekly_payload(s,revision);r=s['results']
    expected=set(spec['models'])
    if set(r['pooled'])!=expected or [b['year'] for b in r['blocks']]!=spec['outer_years']:raise ValueError('Faltan modelos/bloques.')
    if len(r['fits'])!=3 or any(f['last_training_target']>f['cutoff'] or f['ridge_normal_equation_error']>1e-10 for f in r['fits']):raise ValueError('Fit semanal no causal/cerrado.')
    for k,v in r['pooled'].items():
        n=sum(b['metrics'][k]['n'] for b in r['blocks'])
        if v['n']!=n:raise ValueError('Cobertura distinta.')
        for metric in ('mse','mae','direction_accuracy'):
            mean=sum(b['metrics'][k]['n']*b['metrics'][k][metric] for b in r['blocks'])/n
            if not math.isclose(v[metric],mean,abs_tol=1e-12):raise ValueError('Agregación no ponderada.')
        skill=1-v['mse']/r['pooled']['historical_mean']['mse']
        if not math.isclose(skill,v['r2_oos_vs_historical_mean'],abs_tol=1e-12):raise ValueError('Skill alterado.')
    for k,intervals in r['paired_loss_ci'].items():
        if set(intervals)!={'4','12'}:raise ValueError('Sensibilidad bootstrap omitida.')
        for ci in intervals.values():
            if ci['lower_95']>ci['upper_95'] or not math.isclose(ci['mean_loss_difference'],r['pooled'][k]['mse']-r['pooled']['historical_mean']['mse'],abs_tol=1e-12):raise ValueError('Intervalo/diferencia incorrectos.')
    return s


def render(a,w,url):
    lines=['# Auditoría numérica y adaptación semanal — resultados', '',f'Ejecución: {url}', '',
           '**Dos tareas separadas. No se modificó ni se volvió a puntuar el test del experimento anterior. No PnL ni aprobación para operar.**', '',
           '## 1. Hallazgo numérico: diez épocas no resolvían el objetivo de train', '',
           'Se reauditaron los originales y se recuperaron los pesos del artifact del experimento anterior. Las seis reconstrucciones iniciales coinciden dentro de la tolerancia1e-10; fijo/adaptativo compartían ese estado. '
           'Se agregó el primer ajuste interno, con88 ejemplos y25 coeficientes, como diagnóstico.', '',
           'Gradiente analítico, diferencias finitas y pasos de producción concuerdan. Newton y SciPy L-BFGS-B (con derivadas numéricas y otra expresión estable del objetivo) llegan a soluciones compatibles. '
           'No se encontró un error de signo/normalización en estas comprobaciones; no es una prueba de ausencia de cualquier bug.', '',
           '| Caso | n train | Parámetros | J en época10 | J óptimo referencia | Gap | Norma gradiente época10 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for c in a['cases']:
        p=c['trajectory'][2];lines.append(f"| {c['name']} | {c['rows']} | {c['parameters']} | {p['objective']:.6f} | {c['newton_objective']:.6f} | {p['gap_to_optimum']:.6f} | {p['gradient_inf']:.6f} |")
    errors=max(c['gradient_fd_max_error'] for c in a['cases']);dif=max(c['solver_max_weight_difference'] for c in a['cases'])
    lines+=['',f'Error máximo del gradiente frente a diferencias finitas: {errors:.3e}. Diferencia máxima de coeficientes entre solvers: {dif:.3e}. En ningún caso se activó el clipping de logits>=35.', '',
            '**Los siete casos no cumplen la tolerancia de convergencia en época10.** El objetivo de la tabla es log-loss de ENTRENAMIENTO más L2/2, no el log-loss externo. '
            'Las trayectorias0/1/10/100/1000 completas se conservan en audit_summary.json. Con paso constante, SGD puede quedar cerca del óptimo sin llegar a su tolerancia; aumentar épocas a ciegas tampoco certifica convergencia.', '',
            'Esto identifica una limitación del procedimiento: no habíamos verificado su calidad como solución del objetivo declarado. Pero parar temprano puede regularizar implícitamente. '
            '**No demuestra que resolver mejor train mejore test, ni explica causalmente los malos resultados históricos.** No se sustituyen sus scores por los del óptimo.', '',
            '## 2. Adaptación parcial: magnitud de retorno semanal', '',
            'Inspirada en el componente de momentum temporal semanal de Liu/Tsyvinski, NBER24877(2018). No es réplica exacta del artículo, no CTREND transversal y no incluye atención/red ni sus datos originales.', '',
            '- Señal al cierre UTC del domingo. Target: close[t+8]/open[t+2]−1, referencia de siete sesiones de martes a lunes tras un día completo intermedio. No fill garantizado.',
            '- BTCUSDT, no retorno exacto USD ni exceso sobre tasa libre de riesgo. Features: momentum7/28/84 y volatilidad28. Mediana/IQR de train, clipping[-5,5].',
            '- OLS momentum7 y ridge4 con alpha1 fijo, ambos por solución cerrada/lstsq, no SGD. Seis ajustes por pasada, dos pasadas idénticas=12 fits, sin HPO ni selección de horizonte/semilla/umbral.',
            '- Baselines: retorno0 y media histórica solo de etiquetas maduras de train. Ventanas expansivas con92/144/196 semanas de entrenamiento; modelos congelados por año2024/2025/2026.',
            '- Métrica primaria MSE; R²_OOS expresa mejora relativa frente a media histórica. No equivale a rentabilidad. Todas las métricas/cohortes y los dos largos de bootstrap se publican.', '',
            '### Agregado externo: 141 semanas (52/52/37 por año)', '',
            '| Modelo | MSE ↓ | MAE ↓ | R² OOS vs media | Dirección |','|---|---:|---:|---:|---:|']
    for name in ('historical_mean','zero','ols_momentum7','ridge4'):
        m=w['results']['pooled'][name];lines.append(f"| {name} | {m['mse']:.9f} | {m['mae']:.6f} | {m['r2_oos_vs_historical_mean']*100:+.4f}% | {m['direction_accuracy']*100:.2f}% |")
    lines+=['', 'MSE se mide en retorno fraccional al cuadrado y MAE en retorno fraccional. Por ejemplo MAE0.052 significa error absoluto medio de5.2 puntos porcentuales, no ganancia5.2%. Retorno0 tiene dirección siempre «no positivo», no una moneda aleatoria.', '',
            '### Incertidumbre exploratoria emparejada', '',
            'Diferencia de pérdidas cuadráticas modelo−media histórica; negativo favorece modelo. Bootstrap circular dentro de cada año,2000réplicas,seed1701, percentiles95%. '
            'No se corrige multiplicidad ni investigación previa. Ambos largos de bloque se reportan; no son ensayos independientes.', '',
            '| Modelo | Bloque semanas | Diferencia media | IC95% inferior | IC95% superior |','|---|---:|---:|---:|---:|']
    for name,intervals in w['results']['paired_loss_ci'].items():
        for length in ('4','12'):
            ci=intervals[length];lines.append(f"| {name} | {length} | {ci['mean_loss_difference']:+.8f} | {ci['lower_95']:+.8f} | {ci['upper_95']:+.8f} |")
    lines+=['', '### Todos los bloques', '', '| Año | Modelo | n | MSE ↓ | R² OOS vs media |','|---|---|---:|---:|---:|']
    for b in w['results']['blocks']:
        for name,m in b['metrics'].items():lines.append(f"| {b['year']} | {name} | {m['n']} | {m['mse']:.9f} | {m['r2_oos_vs_historical_mean']*100:+.4f}% |")
    lines+=['', '## Lectura y siguiente decisión', '']
    rr=w['results']['pooled']
    lines.append(f"- Ridge tiene R² OOS {rr['ridge4']['r2_oos_vs_historical_mean']*100:+.4f}% frente a media histórica; OLS {rr['ols_momentum7']['r2_oos_vs_historical_mean']*100:+.4f}%. Son porcentajes de reducción de error, NO retorno de una inversión.")
    if rr['zero']['mse']<rr['ridge4']['mse']:lines.append('- Predecir siempre retorno0 obtiene MSE ligeramente mejor que ridge. Una pequeña mejora sobre la media histórica no basta para demostrar señal útil.')
    if all(ci['lower_95']<=0<=ci['upper_95'] for name in ('ols_momentum7','ridge4') for ci in w['results']['paired_loss_ci'][name].values()):lines.append('- Los intervalos de ambos modelos incluyen0 con ambos largos de bloque: esta exploración no establece una ventaja estadística sólida.')
    lines+=['- No se promueve ganador, se cambian métricas ni se reoptimiza alpha/épocas después de ver estos resultados. Para un próximo clasificador, usar solver controlado o justificar explícitamente early stopping dentro de validación, no asumir que diez épocas resuelven el objetivo.',
            '- La adaptación semanal responde otra pregunta. No rescata el experimento de dirección diaria ni constituye una réplica confirmada del paper.',
            '- El histórico ya inspeccionado continúa siendo exploratorio. Confirmación requiere observaciones futuras realmente reservadas. Costos, filtros, liquidez y fills aplicables siguen pendientes: no inferir utilidad paraUSD20.', '',
            '## Integridad y reproducción', '',
            'Protocolos/código publicados antes del cálculo. Reauditoría82 archivos/1730días, sin espejo. Dos Checks separados, mismo commit productor; sus recibos y hashes están en check_receipts.json. '
            'La auditoría usa solo train; la adaptación tiene dos pasadas idénticas en fits, predicciones, métricas e intervalos. Success significa cálculo validado, no éxito financiero.', '',
            '```bash','python -m scripts.fetch_numerical_review','```', '',
            'Recupera agregados existentes por Checks API; no inicia otro runner ni instala paquetes. Audit_summary.json conserva los controles/trajectorias y weekly_summary.json todos los resultados semanales. '
            'Pronósticos semanales completos en el artifact, retención7días. Protocolo y matriz de adaptación: docs/investigacion/16_auditoria_y_adaptacion_semanal.md.', '',
            'Fuente: Binance Vision https://data.binance.vision/; CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial. Informes derivados bajo CC BY-NC-SA4.0. '
            'Términos/atribución en el artifact; sin aval del proveedor. No se ejecutaron Laya, población evolutiva, órdenes ni servicios de inferencia pagados.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--revision',default=REVISION);p.add_argument('--run-id',type=int,default=RUN_ID);o=p.parse_args()
    run=api(f'repos/{REPO}/actions/runs/{o.run_id}');checks=api(f'repos/{REPO}/commits/{o.revision}/check-runs?per_page=100')['check_runs']
    out=Path('artifacts/numerical_review');out.mkdir(parents=True,exist_ok=True);results=[];receipts=[]
    for name,spec_path,validator,file in ((CHECK_NAME,'experiments/numerical_audit.json',validate_audit,'audit_summary.json'),(WEEKLY_CHECK_NAME,'experiments/weekly_return_adaptation.json',validate_weekly,'weekly_summary.json')):
        matches=[c for c in checks if c['name']==name]
        if len(matches)!=1:raise ValueError('Check ausente o ambiguo.')
        c=matches[0];s=validator(c,run,json.loads(Path(spec_path).read_text()),o.revision);results.append(s)
        (out/file).write_text(json.dumps(s,indent=2)+'\n');receipt={k:c[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')}
        receipt.update({'app':c['app']['slug'],'summary_sha256':hashlib.sha256(canonical(s).encode()).hexdigest()});receipts.append(receipt)
    (out/'check_receipts.json').write_text(json.dumps({'run_id':run['id'],'run_url':run['html_url'],'checks':receipts},indent=2)+'\n')
    (out/'informe.md').write_text(render(*results,run['html_url']))
    print(json.dumps({'report':str(out/'informe.md'),'cases':len(results[0]['cases']),'weekly_observations':results[1]['results']['pooled']['ridge4']['n']},indent=2))


if __name__=='__main__':main()
