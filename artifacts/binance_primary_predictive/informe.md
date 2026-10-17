# Predictor fijo vs adaptativo — velas oficiales Binance

**Ejecutado en GitHub y recuperado aquí por API. Solo predicción retrospectiva, no PnL ni trading real.**

Ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39080171438

## Fuente y verificación

- BTCUSDT spot diario, 01-01-2022 a 26-09-2026: **82 archivos, 1.730 días**, reauditados desde los ZIP originales, checksums y recibos del artifact fijado.
- Entrenamiento inicial hasta 31-12-2022. Corte de features desde 01-01-2023; pronóstico de dirección intradía open→close de la sesión i+2. Primer objetivo 03-01-2023.
- Modelos logísticos pequeños, fijos/adaptativos, mismos pesos iniciales. Parámetros registrados antes del cálculo; ninguna búsqueda de hiperparámetros.
- El evaluador usa la probabilidad guardada originalmente; después permite actualizar solo al adaptativo. Este conserva estado entre épocas.
- Control constante p=0,5 y persistencia de la última dirección intradía observada con p=0,55/0,45.

## Resultados

Menor Brier/log-loss es mejor. El acierto direccional no mide rentabilidad. No se selecciona ganador.

| Época | Modelo | n | Brier ↓ | Log-loss ↓ | Acierto |
|---|---|---:|---:|---:|---:|
| diagnostic_2023_2024 | fixed | 729 | 0.275561 | 0.751235 | 50.07% |
| diagnostic_2023_2024 | adaptive | 729 | 0.259015 | 0.712246 | 49.66% |
| diagnostic_2023_2024 | constant_p_0_5 | 729 | 0.250000 | 0.693147 | 48.70% |
| diagnostic_2023_2024 | persistence | 729 | 0.250374 | 0.693906 | 52.13% |
| diagnostic_2025_2026 | fixed | 634 | 0.265764 | 0.727340 | 49.53% |
| diagnostic_2025_2026 | adaptive | 634 | 0.259770 | 0.713289 | 47.48% |
| diagnostic_2025_2026 | constant_p_0_5 | 634 | 0.250000 | 0.693147 | 50.32% |
| diagnostic_2025_2026 | persistence | 634 | 0.255497 | 0.704186 | 47.00% |

Para p=0,5, el desempate `p>0,5` predice siempre «no sube». Su acierto no es el de una moneda simulada; Brier/log-loss sí puntúan la incertidumbre constante 50/50.

## Lectura

**Ni el fijo ni el adaptativo superan el control constante en Brier o log-loss en ninguna época.** El adaptativo reduce el error probabilístico frente al fijo, pero no alcanza la referencia sin información. En 2025–26-09-2026 el acierto es 49,53% fijo y 47,48% adaptativo. No hay evidencia aquí para promoverlos a una estrategia.

Esto evalúa estas features, horizonte y procedimiento: no rechaza universalmente el aprendizaje online. No se ajustan los modelos para mejorar estos mismos resultados ni se inicia una población evolutiva buscando un ganador retrospectivo.

## Auditoría

- 2726 predicciones evaluadas y 1363 actualizaciones después del feedback.
- Dos corridas completas con igualdad exacta de métricas y snapshot inicial. Hash-chains diferentes por sus tiempos reales de escritura, como corresponde.
- El informe agregado fue publicado por GitHub Actions como Check en la revisión ejecutada y recuperado por la API de GitHub. Ya no se necesita descargar el artifact a este entorno para leer resultados.
- Originales y ledgers completos siguen en artifacts de GitHub con retención de siete días. No se han importado aquí todas las velas ni se publicaron series completas en Git.
- Suite local validada, incluidos siete tests offline del adaptador; esos siete también pasaron en el runner antes de usar datos reales. Los tests usan fixtures sintéticos, no sustituyen la auditoría del mercado.

## Lo que no demuestra

- No se calculó saldo desde USD 20, comisiones, spread, slippage, fondeo, retiro ni impuestos. Faltan reglas y costos oficiales aplicables.
- Las velas históricas no son timestamps de publicación ni vintages de feed. Replay causal por índices, no point-in-time certificado ni forward.
- Épocas y BTC ya habían sido inspeccionados: no es un holdout independiente. No se calcula significancia de superioridad ni probabilidad de éxito.
- No se comparó contra el espejo previo ni se certifica que coincida con él. La reauditoría verifica integridad y procedencia de los originales del job fijado.
- PriceUSD Coin Metrics era una métrica de referencia close→close; esta etiqueta Binance es intradía open→close. No comparar sus scores como si solo cambiara el proveedor.
- No se ejecutaron Laya, población evolutiva ni órdenes reales. El gate económico sigue cerrado.

## Licencia y atribución

Fuente: Binance Vision, https://data.binance.vision/. Dataset Terms v1.0 y CC BY-NC-SA 4.0 salvo designación distinta; uso de investigación no comercial. Este informe derivado se comparte bajo CC BY-NC-SA 4.0. Términos y atribución se conservan junto a los originales en GitHub. Sin patrocinio ni aprobación de Binance. No confundir licencia del código con licencia comercial del dataset.

## Reproducción y recuperación

Protocolo: `experiments/binance_primary_predictive.json`. Workflow: `.github/workflows/primary-predictive.yml`. Fuente fijada: run 39079361222, artifact 12117929369; si expira, fallar sin sustituir por otro dataset.

```bash
python -m scripts.fetch_primary_predictive_result
```

El comando recupera agregados existentes; no inicia otra ejecución ni factura un runner. Reentrenar exige correr el workflow de forma explícita, mientras esté disponible el artifact fijado. Checks y source/spec/hash quedan registrados en summary.json y check_receipt.json.
