"""Recupera riesgo histórico ya calculado; no activa la reserva futura."""
import argparse,hashlib,json,math
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import api,REPO
REVISION='107a4120a63d633fd829d232be871190bd396675'
RUN_ID=39085620035
CHECK_NAME='Risk persistence — aggregate report'


def validate(c,run,spec,revision):
    if run.get('head_sha')!=revision or run.get('conclusion')!='success' or run.get('path')!='.github/workflows/risk-persistence.yml':raise ValueError('Workflow/revisión incorrectos.')
    if c.get('head_sha')!=revision or c.get('name')!=CHECK_NAME or c.get('conclusion')!='success' or c.get('app',{}).get('slug')!='github-actions':raise ValueError('Check/productor incorrectos.')
    text=c['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):raise ValueError('Formato incorrecto.')
    s=json.loads(text[8:-4])
    if s['experiment_id']!=spec['id'] or s['source']!=spec['source'] or s['spec_sha256']!=hashlib.sha256(canonical(spec).encode()).hexdigest():raise ValueError('Protocolo/fuente distintos.')
    if s['reproduced'] is not True or any(s.get(k) is not False for k in ('trading_backtest','market_run_enabled','forward_started','historically_pristine_holdout')):raise ValueError('Alcance alterado.')
    if s['data_rows']!=1730 or s['source_audit']['valid_archives']!=82 or any(s['source_audit'][k] for k in ('errors','missing_dates','extra_dates')):raise ValueError('Fuente incompleta.')
    r=s['results']
    if 'records' in r or r['winner_promoted'] is not False or set(r['metrics'])!=set(spec['models']) or [b['test'] for b in r['blocks']]!=spec['blocks']:raise ValueError('Modelos/bloques omitidos.')
    for name,m in r['metrics'].items():
        n=sum(b['metrics'][name]['n'] for b in r['blocks'])
        if m['n']!=n or n!=1365:raise ValueError('Cobertura incorrecta.')
        for metric in ('qlike','mse','mean_forecast','mean_proxy'):
            v=sum(b['metrics'][name]['n']*b['metrics'][name][metric] for b in r['blocks'])/n
            if not math.isfinite(m[metric]) or not math.isclose(m[metric],v,abs_tol=1e-12):raise ValueError('Agregación incorrecta.')
    if set(r['paired_ci_vs_rolling20'])!={'ewma94','rolling60','range20'}:raise ValueError('Comparaciones omitidas.')
    for name,intervals in r['paired_ci_vs_rolling20'].items():
        if set(intervals)!={'14','60'}:raise ValueError('Largo de bloque omitido.')
        for ci in intervals.values():
            if ci['lower95']>ci['upper95'] or not math.isclose(ci['delta_qlike'],r['metrics'][name]['qlike']-r['metrics']['rolling20']['qlike'],abs_tol=1e-12):raise ValueError('Diferencia alterada.')
    return s


def render(s,url):
    r=s['results'];lines=['# Hipótesis de riesgo: persistencia y reserva futura', '',f'Ejecución histórica: {url}', '',
        '**Nueva pregunta: tamaño cuadrático del retorno, NO dirección ni rentabilidad. Solo diagnóstico retrospectivo; reserva futura aún sin activar.**', '',
        '## Reglas fijadas antes del cálculo', '',
        '- Originales oficiales BTCUSDT,82 archivos/1730días. Forecast con datos hasta t−2; target log(close[t]/close[t−1])². Proxy ruidoso de segundo momento, no varianza latente observada. Interpretación como varianza requiere media condicional despreciable.',
        '- Cinco métodos sin HPO: constante media2022 hasta30diciembre; medias móviles20/60 de r²; EWMA lambda0.94 inicializado con60retornos; rango20 mean(log(H/L)²/(4log2)). Rango presupone dinámica de difusión, sin garantía de ausencia de drift/jumps.',
        '- QLIKE primaria=log(h)+y/h. Se omiten constantes comunes al outcome. **Puede ser negativa: menor es mejor.** No convertir cocientes QLIKE en porcentajes de mejora. MSE del proxy secundaria.',
        '- Dos pasadas idénticas. Todos los métodos/períodos publicados, sin elegir ganador. No es HAR-RV: faltan datos intradiarios de realized variance.', '',
        '## Agregado:1.365 targets de2023 a26-09-2026', '',
        '| Método | QLIKE ↓ | MSE ↓ | Media forecast | Media proxy |','|---|---:|---:|---:|---:|']
    for name in ('constant_train','rolling20','rolling60','ewma94','range20'):
        m=r['metrics'][name];lines.append(f"| {name} | {m['qlike']:.6f} | {m['mse']:.9e} | {m['mean_forecast']:.7f} | {m['mean_proxy']:.7f} |")
    delta=r['metrics']['ewma94']['qlike']-r['metrics']['rolling20']['qlike']
    mse_improvement=1-r['metrics']['ewma94']['mse']/r['metrics']['rolling20']['mse']
    lines+=['',f'EWMA94−rolling20: ΔQLIKE={delta:+.6f}. Reducción de MSE={mse_improvement*100:.2f}% frente a rolling20. Este porcentaje es reducción de error, **no rentabilidad**.', '',
        '## Incertidumbre exploratoria, todas las comparaciones', '',
        'Diferencias QLIKE método−rolling20; negativo favorece método. Bootstrap circular dentro de cada bloque,2000réplicas,seed1701,14/60días. Sin corrección por multiplicidad ni investigación previa, no prueba confirmatoria.', '',
        '| Método | Bloque días | Delta | Inferior95% | Superior95% |','|---|---:|---:|---:|---:|']
    for name,intervals in r['paired_ci_vs_rolling20'].items():
        for length in ('14','60'):
            ci=intervals[length];lines.append(f"| {name} | {length} | {ci['delta_qlike']:+.6f} | {ci['lower95']:+.6f} | {ci['upper95']:+.6f} |")
    lines+=['', '## Todos los bloques', '', '| Período | Método | n | QLIKE ↓ | MSE ↓ |','|---|---|---:|---:|---:|']
    for b in r['blocks']:
        for name,m in b['metrics'].items():lines.append(f"| {' a '.join(b['test'])} | {name} | {m['n']} | {m['qlike']:.6f} | {m['mse']:.9e} |")
    lines+=['', '## Qué significa y qué no', '',
        '- El diagnóstico permite estudiar predictibilidad del riesgo por separado de dirección. No rescata el clasificador anterior ni implica una estrategia rentable.',
        '- EWMA no es uniformemente el mejor método en cada período. También hay otros métodos que pueden mejorar al benchmark; no se proclama ganador universal.',
        '- QLIKE/MSE tienen fundamentos para proxies bajo supuestos: no certificamos insesgadez condicional del proxy BTC. Dos días de horizonte, ruido, no estacionariedad y tamaño muestral limitan las conclusiones.',
        '- No se calcula VaR/ES calibrado, Sharpe, posiciones o PnL USD20. Menor error de riesgo puede servir para investigar límites de exposición, pero falta política y costos verificables.', '',
        '## Reserva futura, no resultados futuros', '',
        '**01-11-2026 a31-01-2027:92targets diarios UTC.** EWMA94 challenger primario y rolling20 referencia, elegidos en el protocolo ANTES del histórico; no cambiar por el ganador observado. Mantener los cinco métodos en el reporte.',
        '- Para target D: input oficial completo hasta cierre D−2, emisión/publicación en D−1 UTC antes de D00:00. No backfill; registrar cada falta/retraso entre las92 fechas.',
        '- El guard local de creación exclusiva está implementado/probado con fixtures; un archivo local no acredita publicación prospectiva.',
        '- Check.completed_at por sí solo no basta: la API permite suministrarlo/editar output. Antes de activar se requiere artifact ID/digest vinculado a bytes, created_at del servicio antes del target y workflow/head/protocolo correctos, con verificación de bytes.',
        '- **No hay cron, colección ni publicación futura habilitada.** Falta integrar adquisición fresca/publicación y conservación verificable de evidencia durante toda la reserva; la retención7días histórica es insuficiente. No se autoriza almacenamiento recurrente pagado.',
        '- No actualizar métodos por resultados parciales. Análisis al final de la ventana; incluso entonces se deben declarar cobertura, missingness y supuestos.', '',
        '## Trazabilidad', '',
        'Protocolo histórico y código publicados antes del cálculo; dos pasadas idénticas en cada forecast/outcome/métrica/intervalo. Historial ya inspeccionado, no holdout virgen. Success significa ejecución/controles completados, no aprobación financiera.', '',
        'Registros completos en artifact con retención7días; agregados/recibo en Git. Protocolos: experiments/risk_persistence.json y experiments/risk_forward_reserved.json; fuentes y matriz de hipótesis en docs/investigacion/18_hipotesis_de_riesgo_y_reserva_futura.md.', '',
        '```bash','python -m scripts.fetch_risk_result','```', '',
        'Solo recupera resultados existentes por Checks API; no inicia cálculos ni reserva activa. Datos: Binance Vision https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial; informe derivado bajo CC BY-NC-SA4.0. Atribución/términos en artifact; sin aval del proveedor.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--revision',default=REVISION);p.add_argument('--run-id',type=int,default=RUN_ID);a=p.parse_args()
    run=api(f'repos/{REPO}/actions/runs/{a.run_id}');checks=api(f'repos/{REPO}/commits/{a.revision}/check-runs?per_page=100')['check_runs'];matches=[c for c in checks if c['name']==CHECK_NAME]
    if len(matches)!=1:raise ValueError('Check ausente/ambiguo.')
    c=matches[0];s=validate(c,run,json.loads(Path('experiments/risk_persistence.json').read_text()),a.revision)
    out=Path('artifacts/risk_persistence');out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(s,indent=2)+'\n');(out/'informe.md').write_text(render(s,run['html_url']))
    receipt={k:c[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')};receipt.update({'run_id':run['id'],'run_url':run['html_url'],'app':c['app']['slug'],'summary_sha256':hashlib.sha256(canonical(s).encode()).hexdigest()})
    (out/'check_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'report':str(out/'informe.md'),'forward_started':False},indent=2))


if __name__=='__main__':main()
