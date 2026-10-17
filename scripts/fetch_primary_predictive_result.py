"""Recupera agregados por GitHub Checks API, sin tocar hosts de artifact storage."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from microtrade.online import canonical

REPO = 'joaquinignaciomondaca-code/Idea_3'
REVISION = '0be6d81569462d3956d1d5f476a1fa0dd3fb4dfd'
RUN_ID = 39080171438
CHECK_NAME = 'Primary predictive replay — aggregate report'


def api(endpoint):
    return json.loads(subprocess.run(['gh', 'api', endpoint], capture_output=True, check=True).stdout)


def validate_result(check, workflow_run, spec, revision):
    if workflow_run.get('head_sha') != revision or workflow_run.get('conclusion') != 'success':
        raise ValueError('Workflow no exitoso o de otra revisión.')
    if check.get('head_sha') != revision or check.get('name') != CHECK_NAME or check.get('conclusion') != 'success' or check.get('app', {}).get('slug') != 'github-actions':
        raise ValueError('Check no corresponde al productor/revisión/estado esperado.')
    text = check['output']['text']
    if not text.startswith('```json\n') or not text.endswith('\n```'):
        raise ValueError('Formato de agregados inválido.')
    summary = json.loads(text[8:-4])
    if summary.get('experiment_id') != spec['id'] or summary.get('source') != spec['source']:
        raise ValueError('Experimento/fuente diferentes.')
    if summary.get('spec_sha256') != hashlib.sha256(canonical(spec).encode()).hexdigest():
        raise ValueError('Protocolo remoto diferente.')
    if (summary.get('trading_backtest') is not False or summary.get('market_run_enabled') is not False or
            summary.get('repeated_metrics_equal') is not True or 'observations' in summary or 'accounts' in summary):
        raise ValueError('Resultado fuera del alcance permitido.')
    return summary


def render(summary, run_url):
    md = ['# Predictor fijo vs adaptativo — velas oficiales Binance', '',
          '**Ejecutado en GitHub y recuperado aquí por API. Solo predicción retrospectiva, no PnL ni trading real.**', '',
          f'Ejecución: {run_url}', '',
          '## Fuente y verificación', '',
          '- BTCUSDT spot diario, 01-01-2022 a 26-09-2026: **82 archivos, 1.730 días**, reauditados desde los ZIP originales, checksums y recibos del artifact fijado.',
          '- Entrenamiento inicial hasta 31-12-2022. Corte de features desde 01-01-2023; pronóstico de dirección intradía open→close de la sesión i+2. Primer objetivo 03-01-2023.',
          '- Modelos logísticos pequeños, fijos/adaptativos, mismos pesos iniciales. Parámetros registrados antes del cálculo; ninguna búsqueda de hiperparámetros.',
          '- El evaluador usa la probabilidad guardada originalmente; después permite actualizar solo al adaptativo. Este conserva estado entre épocas.',
          '- Control constante p=0,5 y persistencia de la última dirección intradía observada con p=0,55/0,45.', '',
          '## Resultados', '',
          'Menor Brier/log-loss es mejor. El acierto direccional no mide rentabilidad. No se selecciona ganador.', '',
          '| Época | Modelo | n | Brier ↓ | Log-loss ↓ | Acierto |',
          '|---|---|---:|---:|---:|---:|']
    for epoch, models in summary['metrics'].items():
        for name in ('fixed', 'adaptive', 'constant_p_0_5', 'persistence'):
            r = models[name]
            md.append(f"| {epoch} | {name} | {r['n']} | {r['brier']:.6f} | {r['log_loss']:.6f} | {r['accuracy']*100:.2f}% |")
    md += ['', 'Para p=0,5, el desempate `p>0,5` predice siempre «no sube». Su acierto no es el de una moneda simulada; Brier/log-loss sí puntúan la incertidumbre constante 50/50.', '',
           '## Lectura', '',
           '**Ni el fijo ni el adaptativo superan el control constante en Brier o log-loss en ninguna época.** '
           'El adaptativo reduce el error probabilístico frente al fijo, pero no alcanza la referencia sin información. '
           'En 2025–26-09-2026 el acierto es 49,53% fijo y 47,48% adaptativo. No hay evidencia aquí para promoverlos a una estrategia.', '',
           'Esto evalúa estas features, horizonte y procedimiento: no rechaza universalmente el aprendizaje online. '
           'No se ajustan los modelos para mejorar estos mismos resultados ni se inicia una población evolutiva buscando un ganador retrospectivo.', '',
           '## Auditoría', '',
           f"- {summary['audit']['predictions']} predicciones evaluadas y {summary['audit']['adaptive_updates']} actualizaciones después del feedback.",
           '- Dos corridas completas con igualdad exacta de métricas y snapshot inicial. Hash-chains diferentes por sus tiempos reales de escritura, como corresponde.',
           '- El informe agregado fue publicado por GitHub Actions como Check en la revisión ejecutada y recuperado por la API de GitHub. Ya no se necesita descargar el artifact a este entorno para leer resultados.',
           '- Originales y ledgers completos siguen en artifacts de GitHub con retención de siete días. No se han importado aquí todas las velas ni se publicaron series completas en Git.',
           '- Suite local validada, incluidos siete tests offline del adaptador; esos siete también pasaron en el runner antes de usar datos reales. Los tests usan fixtures sintéticos, no sustituyen la auditoría del mercado.', '',
           '## Lo que no demuestra', '',
           '- No se calculó saldo desde USD 20, comisiones, spread, slippage, fondeo, retiro ni impuestos. Faltan reglas y costos oficiales aplicables.',
           '- Las velas históricas no son timestamps de publicación ni vintages de feed. Replay causal por índices, no point-in-time certificado ni forward.',
           '- Épocas y BTC ya habían sido inspeccionados: no es un holdout independiente. No se calcula significancia de superioridad ni probabilidad de éxito.',
           '- No se comparó contra el espejo previo ni se certifica que coincida con él. La reauditoría verifica integridad y procedencia de los originales del job fijado.',
           '- PriceUSD Coin Metrics era una métrica de referencia close→close; esta etiqueta Binance es intradía open→close. No comparar sus scores como si solo cambiara el proveedor.',
           '- No se ejecutaron Laya, población evolutiva ni órdenes reales. El gate económico sigue cerrado.', '',
           '## Licencia y atribución', '',
           'Fuente: Binance Vision, https://data.binance.vision/. Dataset Terms v1.0 y CC BY-NC-SA 4.0 salvo designación distinta; '
           'uso de investigación no comercial. Este informe derivado se comparte bajo CC BY-NC-SA 4.0. '
           'Términos y atribución se conservan junto a los originales en GitHub. Sin patrocinio ni aprobación de Binance. No confundir licencia del código con licencia comercial del dataset.', '',
           '## Reproducción y recuperación', '',
           'Protocolo: `experiments/binance_primary_predictive.json`. Workflow: `.github/workflows/primary-predictive.yml`. '
           'Fuente fijada: run 39079361222, artifact 12117929369; si expira, fallar sin sustituir por otro dataset.', '',
           '```bash', 'python -m scripts.fetch_primary_predictive_result', '```', '',
           'El comando recupera agregados existentes; no inicia otra ejecución ni factura un runner. '
           'Reentrenar exige correr el workflow de forma explícita, mientras esté disponible el artifact fijado. '
           'Checks y source/spec/hash quedan registrados en summary.json y check_receipt.json.', '']
    return '\n'.join(md)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=REVISION)
    parser.add_argument('--run-id', type=int, default=RUN_ID)
    args = parser.parse_args()
    spec = json.loads(Path('experiments/binance_primary_predictive.json').read_text())
    workflow_run = api(f'repos/{REPO}/actions/runs/{args.run_id}')
    if workflow_run['id'] != args.run_id or workflow_run.get('path') != '.github/workflows/primary-predictive.yml':
        raise ValueError('Workflow diferente al esperado.')
    checks = api(f'repos/{REPO}/commits/{args.revision}/check-runs?per_page=100')['check_runs']
    matches = [c for c in checks if c['name'] == CHECK_NAME]
    if len(matches) != 1:
        raise ValueError('Check ausente o ambiguo; revisar intentos explícitamente.')
    check = matches[0]; summary = validate_result(check, workflow_run, spec, args.revision)
    out = Path('artifacts/binance_primary_predictive'); out.mkdir(parents=True, exist_ok=True)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    receipt = {k: check[k] for k in ('id','name','head_sha','conclusion','html_url','started_at','completed_at')}
    receipt.update({'run_id': args.run_id, 'run_url': workflow_run['html_url'],
                    'workflow_path': workflow_run['path'], 'app': check['app']['slug'],
                    'summary_sha256': hashlib.sha256(canonical(summary).encode()).hexdigest()})
    (out/'check_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    (out/'informe.md').write_text(render(summary, workflow_run['html_url']))
    print(json.dumps({'run': workflow_run['html_url'], 'check_id': check['id'],
                      'predictions': summary['audit']['predictions'], 'report': str(out/'informe.md')},indent=2))


if __name__ == '__main__':
    main()
