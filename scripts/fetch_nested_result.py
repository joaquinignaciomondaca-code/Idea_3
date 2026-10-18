"""Recupera el estudio anidado por Checks API. No inicia nuevos trials ni runners."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import api, REPO

REVISION = 'df5658a493e1224426dcf62af3d77956658bf53f'
RUN_ID = 39081333060
CHECK_NAME = 'Nested Optuna predictive — aggregate report'


def validate_result(check, run, spec, revision):
    if run.get('head_sha') != revision or run.get('conclusion') != 'success' or run.get('path') != '.github/workflows/nested-optuna.yml':
        raise ValueError('Workflow/revisión/estado inesperado.')
    if check.get('head_sha') != revision or check.get('name') != CHECK_NAME or check.get('conclusion') != 'success' or check.get('app', {}).get('slug') != 'github-actions':
        raise ValueError('Check no corresponde a la ejecución esperada.')
    text = check['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):
        raise ValueError('Formato incorrecto.')
    summary = json.loads(text[8:-4])
    if summary.get('experiment_id') != spec['id'] or summary.get('source') != spec['source'] or summary.get('spec_sha256') != hashlib.sha256(canonical(spec).encode()).hexdigest():
        raise ValueError('Fuente o protocolo remoto diferente.')
    if summary.get('reproduced') is not True or summary.get('trading_backtest') is not False or summary.get('market_run_enabled') is not False or summary.get('costs_verified') is not False:
        raise ValueError('Resultado fuera del alcance permitido.')
    result = summary['results']
    if any(result.get(flag) is not False for flag in ('trading_backtest', 'winner_promoted', 'historically_pristine_holdout')):
        raise ValueError('Alcance retrospectivo alterado.')
    trials = [t for s in result['selections'] for t in s['trials']]
    if result['total_trials'] != spec['trial_budget']['total'] or len(trials) != spec['trial_budget']['total'] or 'outer_predictions' in result:
        raise ValueError('Presupuesto incompleto o predicciones individuales en agregados.')
    expected_pairs = {(b['name'], m) for b in spec['outer_blocks'] for m in spec['models']}
    if {(s['block'],s['mode']) for s in result['selections']} != expected_pairs or len(result['selections']) != len(expected_pairs):
        raise ValueError('Selecciones faltantes o repetidas.')
    for selection in result['selections']:
        if [t['number'] for t in selection['trials']] != list(range(spec['trial_budget']['per_model_per_outer_block'])):
            raise ValueError('Trials omitidos.')
        for trial in selection['trials']:
            objective = sum(n*loss for n, loss in zip(trial['fold_n'], trial['fold_losses']))/sum(trial['fold_n'])
            if not math.isfinite(trial['value']) or not math.isclose(objective, trial['value'], rel_tol=1e-14):
                raise ValueError('Objetivo no coincide con validación interna.')
        best = min(selection['trials'],key=lambda t:(t['value'],t['number']))
        if selection['selected_trial'] != best['number'] or selection['selected_params'] != best['params']:
            raise ValueError('Se eligió usando otra regla.')
    return summary


def render(s, run_url):
    results = s['results']; pooled = results['pooled_outer_metrics']
    md = ['# Optuna temporal anidado — primera búsqueda acotada', '',
          '**Ejecutado con velas oficiales. Solo predicción retrospectiva; no PnL ni estrategia aprobada.**', '',
          f'Ejecución: {run_url}', '',
          '## Diseño congelado antes del cálculo', '',
          '- 30 intentos: 5 por modelo (fijo/adaptativo) y por bloque externo (2023, 2024, 2025–26-09-2026). Se repitió la búsqueda completa con las mismas semillas para comprobar determinismo, no para elegir otra búsqueda.',
          '- Optuna 4.5.0 TPE, dos propuestas de arranque por estudio, una tarea a la vez, sin pruning. Es un piloto pequeño: no demuestra óptimo global ni superioridad de TPE sobre búsqueda aleatoria.',
          '- Hiperparámetros: learning rate [0,001;0,05] logarítmico, L2 [0,00001;0,1] logarítmico, últimos 90/180/365 ejemplos de entrenamiento elegibles. Diez épocas fijas; intercepto no regularizado.',
          '- Objetivo: log-loss ponderado por observaciones de dos bloques de validación internos anteriores al test. Dispersión interna registrada como diagnóstico; no se ajustaron penalizaciones después de ver resultados.',
          '- En cada bloque externo se seleccionan ambas configuraciones antes de evaluar cualquiera. El optimizador recibe un prefijo separado que termina en test_start−2. Solo se entrenan etiquetas completas; los hiperparámetros quedan congelados durante ese bloque externo.',
          '- Los pesos se reinician en cada bloque. El adaptativo aprende después del feedback; el fijo no. La ventana controla el ajuste inicial, no un refit periódico.',
          '- Controles sin optimizar: misma estructura externa, tasa 0,02, L2=0 y ventana 365. También p=0,5 y persistencia con p=0,55/0,45. No comparar directamente con el replay anterior que mantenía estado desde 2022.', '',
          '## Resultados externos concatenados', '',
          'Cada predictor tiene 1.365 etiquetas, de 01-01-2023 a 26-09-2026. Brier y log-loss menores son mejores. '
          'La agregación usa todas las predicciones externas, no un promedio sin ponderar de bloques con distinta longitud.', '',
          '| Predictor | Log-loss ↓ | Brier ↓ | Acierto |', '|---|---:|---:|---:|']
    for name in ('fixed_tuned','fixed_untuned','adaptive_tuned','adaptive_untuned','constant_p0_5','persistence'):
        r = pooled[name]; md.append(f"| {name} | {r['log_loss']:.6f} | {r['brier']:.6f} | {r['accuracy']*100:.2f}% |")
    md += ['', 'El desempate de p=0,5 elige siempre «no sube»; su acierto no corresponde a una moneda simulada. La puntuación probabilística sí representa incertidumbre 50/50.', '',
           '## Todos los bloques, sin selección de períodos', '',
           '| Bloque | Predictor | n | Log-loss ↓ | Brier ↓ |', '|---|---|---:|---:|---:|']
    for block in results['blocks']:
        for name in ('fixed_tuned','fixed_untuned','adaptive_tuned','adaptive_untuned','constant_p0_5','persistence'):
            r = block['metrics'][name]
            md.append(f"| {block['name']} | {name} | {r['n']} | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    md += ['', '## Configuración seleccionada solo con validación interna', '',
           '| Bloque | Modelo | Trial | Learning rate | L2 | Ventana | Log-loss interno |',
           '|---|---|---:|---:|---:|---:|---:|']
    for choice in results['selections']:
        p = choice['selected_params']
        md.append(f"| {choice['block']} | {choice['mode']} | {choice['selected_trial']} | {p['learning_rate']:.8f} | {p['l2']:.8f} | {p['window']} | {choice['inner_loss']:.6f} |")
    md += ['', 'Los 30 intentos completos, pérdidas por fold y tamaños efectivos están en summary.json. Las ventanas se recortan al pasado realmente disponible cuando aún no hay suficientes ejemplos; nunca se completan con futuro.', '',
           '## Conclusión acotada', '']
    for mode in ('fixed','adaptive'):
        tuned, control = pooled[mode+'_tuned'], pooled[mode+'_untuned']
        md.append(f"- {mode}: log-loss agregado {control['log_loss']:.6f} sin ajustar → {tuned['log_loss']:.6f} ajustado.")
    if all(pooled[m+'_tuned']['log_loss'] >= pooled['constant_p0_5']['log_loss'] for m in ('fixed','adaptive')):
        md.append('- **Ambos optimizados siguen por debajo de p=0,5 en log-loss agregado.** Mejorar al control sin ajustar no demuestra señal predictiva útil.')
    else:
        md.append('- Algún score agregado mejora p=0,5; no implica significancia, rentabilidad ni una estrategia validada.')
    md += ['- La mejora no es uniforme entre bloques; no se oculta el bloque donde optimizar perjudicó al fijo frente a su control. No se promueve una configuración ni se amplía el espacio después de ver estos resultados.', '',
           '## Integridad y límites', '',
           f"- Originales reauditorados: {s['source_audit']['valid_archives']} archivos y {s['data_rows']} días. Fuente: artifact fijado del run 39079361222, con su digest, ZIP, checksums y recibos.",
           f"- Ledger externo: {s['audit']['predictions']} predicciones de los cuatro modelos aprendidos, {s['audit']['updates']} actualizaciones posteriores al feedback. Los dos controles adicionales se puntúan sobre las mismas etiquetas.",
           '- Se auditaron hash-chain, features, pesos, p original, etiquetas, scores y updates. Dos corridas reprodujeron todos los trials, selecciones, pronósticos y métricas. No es un timestamp externo de pronósticos históricos.',
           '- Los 30 intentos se evaluaron dos veces: 60 evaluaciones de objetivo en total, con dos folds internos por intento, además de los ajustes/pruebas externas. No se presentan como solo 30 ejecuciones de modelo.',
           '- El histórico BTC ya había sido inspeccionado. Externo significa excluido de la selección de ese bloque, no holdout históricamente intacto ni forward prospectivo.',
           '- No se verificaron tiempos de publicación/vintages. No se calculó significancia ni se trataron observaciones temporales como independientes.',
           '- No hay Sharpe, PnL de USD 20, stops ni operaciones: faltan costos/filtros aplicables. No se ejecutaron Laya ni evolución poblacional.',
           '- Artifacts de GitHub retienen los registros completos siete días. El informe agregado se recupera por Checks API y se conserva en Git; no se subieron series completas.', '',
           '## Fuente, licencia y reproducción', '',
           'Datos: Binance Vision, https://data.binance.vision/, términos del dataset v1.0/CC BY-NC-SA 4.0 salvo designación distinta. Investigación no comercial. '
           'Este informe derivado se comparte bajo CC BY-NC-SA 4.0; no hay patrocinio ni aprobación del proveedor. Términos y atribución junto a los registros en GitHub.', '',
           'Optuna oficial: https://github.com/optuna/optuna/tree/v4.5.0. Las dependencias se fijan en requirements-optuna.txt y las versiones efectivas constan en summary.json.', '',
           '```bash', 'python -m scripts.fetch_nested_result', '```', '',
           'Este comando recupera agregados existentes; no inicia otra búsqueda. Protocolo: experiments/nested_optuna_predictive.json. '
           'Workflow: .github/workflows/nested-optuna.yml. Si expira el artifact de entrada, el replay falla sin sustituirlo silenciosamente por otro.', '']
    return '\n'.join(md)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=REVISION); parser.add_argument('--run-id', type=int, default=RUN_ID)
    args = parser.parse_args(); spec = json.loads(Path('experiments/nested_optuna_predictive.json').read_text())
    run = api(f'repos/{REPO}/actions/runs/{args.run_id}')
    checks = api(f'repos/{REPO}/commits/{args.revision}/check-runs?per_page=100')['check_runs']
    matches = [c for c in checks if c['name'] == CHECK_NAME]
    if len(matches) != 1:
        raise ValueError('Check ausente o ambiguo.')
    check = matches[0]; s = validate_result(check, run, spec, args.revision)
    out = Path('artifacts/nested_optuna'); out.mkdir(parents=True, exist_ok=True)
    (out/'summary.json').write_text(json.dumps(s, indent=2)+'\n')
    receipt = {k: check[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')}
    receipt.update({'run_id': run['id'], 'run_url': run['html_url'], 'app': check['app']['slug'],
                    'summary_sha256': hashlib.sha256(canonical(s).encode()).hexdigest()})
    (out/'check_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    (out/'informe.md').write_text(render(s, run['html_url']))
    print(json.dumps({'run': run['html_url'], 'trials': s['results']['total_trials'], 'reproduced': s['reproduced'],
                      'report': str(out/'informe.md')},indent=2))


if __name__ == '__main__':
    main()
