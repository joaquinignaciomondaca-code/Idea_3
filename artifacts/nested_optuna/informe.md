# Optuna temporal anidado — primera búsqueda acotada

**Ejecutado con velas oficiales. Solo predicción retrospectiva; no PnL ni estrategia aprobada.**

Ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39081333060

## Diseño congelado antes del cálculo

- 30 intentos: 5 por modelo (fijo/adaptativo) y por bloque externo (2023, 2024, 2025–26-09-2026). Se repitió la búsqueda completa con las mismas semillas para comprobar determinismo, no para elegir otra búsqueda.
- Optuna 4.5.0 TPE, dos propuestas de arranque por estudio, una tarea a la vez, sin pruning. Es un piloto pequeño: no demuestra óptimo global ni superioridad de TPE sobre búsqueda aleatoria.
- Hiperparámetros: learning rate [0,001;0,05] logarítmico, L2 [0,00001;0,1] logarítmico, últimos 90/180/365 ejemplos de entrenamiento elegibles. Diez épocas fijas; intercepto no regularizado.
- Objetivo: log-loss ponderado por observaciones de dos bloques de validación internos anteriores al test. Dispersión interna registrada como diagnóstico; no se ajustaron penalizaciones después de ver resultados.
- En cada bloque externo se seleccionan ambas configuraciones antes de evaluar cualquiera. El optimizador recibe un prefijo separado que termina en test_start−2. Solo se entrenan etiquetas completas; los hiperparámetros quedan congelados durante ese bloque externo.
- Los pesos se reinician en cada bloque. El adaptativo aprende después del feedback; el fijo no. La ventana controla el ajuste inicial, no un refit periódico.
- Controles sin optimizar: misma estructura externa, tasa 0,02, L2=0 y ventana 365. También p=0,5 y persistencia con p=0,55/0,45. No comparar directamente con el replay anterior que mantenía estado desde 2022.

## Resultados externos concatenados

Cada predictor tiene 1.365 etiquetas, de 01-01-2023 a 26-09-2026. Brier y log-loss menores son mejores. La agregación usa todas las predicciones externas, no un promedio sin ponderar de bloques con distinta longitud.

| Predictor | Log-loss ↓ | Brier ↓ | Acierto |
|---|---:|---:|---:|
| fixed_tuned | 0.699074 | 0.252853 | 48.86% |
| fixed_untuned | 0.709301 | 0.257304 | 51.06% |
| adaptive_tuned | 0.698365 | 0.252538 | 49.45% |
| adaptive_untuned | 0.713439 | 0.259731 | 47.91% |
| constant_p0_5 | 0.693147 | 0.250000 | 49.38% |
| persistence | 0.698834 | 0.252830 | 49.67% |

El desempate de p=0,5 elige siempre «no sube»; su acierto no corresponde a una moneda simulada. La puntuación probabilística sí representa incertidumbre 50/50.

## Todos los bloques, sin selección de períodos

| Bloque | Predictor | n | Log-loss ↓ | Brier ↓ |
|---|---|---:|---:|---:|
| outer_2023 | fixed_tuned | 365 | 0.707990 | 0.257042 |
| outer_2023 | fixed_untuned | 365 | 0.737535 | 0.269670 |
| outer_2023 | adaptive_tuned | 365 | 0.703354 | 0.254870 |
| outer_2023 | adaptive_untuned | 365 | 0.715154 | 0.260387 |
| outer_2023 | constant_p0_5 | 365 | 0.693147 | 0.250000 |
| outer_2023 | persistence | 365 | 0.694599 | 0.250719 |
| outer_2024 | fixed_tuned | 366 | 0.693470 | 0.250163 |
| outer_2024 | fixed_untuned | 366 | 0.691623 | 0.249244 |
| outer_2024 | adaptive_tuned | 366 | 0.693611 | 0.250232 |
| outer_2024 | adaptive_untuned | 366 | 0.711893 | 0.258977 |
| outer_2024 | constant_p0_5 | 366 | 0.693147 | 0.250000 |
| outer_2024 | persistence | 366 | 0.693786 | 0.250314 |
| outer_2025_2026 | fixed_tuned | 634 | 0.697177 | 0.251995 |
| outer_2025_2026 | fixed_untuned | 634 | 0.703251 | 0.254838 |
| outer_2025_2026 | adaptive_tuned | 634 | 0.698238 | 0.252527 |
| outer_2025_2026 | adaptive_untuned | 634 | 0.713344 | 0.259788 |
| outer_2025_2026 | constant_p0_5 | 634 | 0.693147 | 0.250000 |
| outer_2025_2026 | persistence | 634 | 0.704186 | 0.255497 |

## Configuración seleccionada solo con validación interna

| Bloque | Modelo | Trial | Learning rate | L2 | Ventana | Log-loss interno |
|---|---|---:|---:|---:|---:|---:|
| outer_2023 | fixed | 3 | 0.00113151 | 0.04194752 | 90 | 0.686215 |
| outer_2023 | adaptive | 4 | 0.00110291 | 0.00003886 | 90 | 0.686230 |
| outer_2024 | fixed | 4 | 0.00105801 | 0.08495120 | 180 | 0.698620 |
| outer_2024 | adaptive | 3 | 0.00103194 | 0.00001304 | 365 | 0.698083 |
| outer_2025_2026 | fixed | 4 | 0.00105970 | 0.03131042 | 365 | 0.689569 |
| outer_2025_2026 | adaptive | 4 | 0.00237193 | 0.00001309 | 365 | 0.691830 |

Los 30 intentos completos, pérdidas por fold y tamaños efectivos están en summary.json. Las ventanas se recortan al pasado realmente disponible cuando aún no hay suficientes ejemplos; nunca se completan con futuro.

## Conclusión acotada

- fixed: log-loss agregado 0.709301 sin ajustar → 0.699074 ajustado.
- adaptive: log-loss agregado 0.713439 sin ajustar → 0.698365 ajustado.
- **Ambos optimizados siguen por debajo de p=0,5 en log-loss agregado.** Mejorar al control sin ajustar no demuestra señal predictiva útil.
- La mejora no es uniforme entre bloques; no se oculta el bloque donde optimizar perjudicó al fijo frente a su control. No se promueve una configuración ni se amplía el espacio después de ver estos resultados.

## Integridad y límites

- Originales reauditorados: 82 archivos y 1730 días. Fuente: artifact fijado del run 39079361222, con su digest, ZIP, checksums y recibos.
- Ledger externo: 5460 predicciones de los cuatro modelos aprendidos, 2730 actualizaciones posteriores al feedback. Los dos controles adicionales se puntúan sobre las mismas etiquetas.
- Se auditaron hash-chain, features, pesos, p original, etiquetas, scores y updates. Dos corridas reprodujeron todos los trials, selecciones, pronósticos y métricas. No es un timestamp externo de pronósticos históricos.
- Los 30 intentos se evaluaron dos veces: 60 evaluaciones de objetivo en total, con dos folds internos por intento, además de los ajustes/pruebas externas. No se presentan como solo 30 ejecuciones de modelo.
- El histórico BTC ya había sido inspeccionado. Externo significa excluido de la selección de ese bloque, no holdout históricamente intacto ni forward prospectivo.
- No se verificaron tiempos de publicación/vintages. No se calculó significancia ni se trataron observaciones temporales como independientes.
- No hay Sharpe, PnL de USD 20, stops ni operaciones: faltan costos/filtros aplicables. No se ejecutaron Laya ni evolución poblacional.
- Artifacts de GitHub retienen los registros completos siete días. El informe agregado se recupera por Checks API y se conserva en Git; no se subieron series completas.

## Fuente, licencia y reproducción

Datos: Binance Vision, https://data.binance.vision/, términos del dataset v1.0/CC BY-NC-SA 4.0 salvo designación distinta. Investigación no comercial. Este informe derivado se comparte bajo CC BY-NC-SA 4.0; no hay patrocinio ni aprobación del proveedor. Términos y atribución junto a los registros en GitHub.

Optuna oficial: https://github.com/optuna/optuna/tree/v4.5.0. Las dependencias se fijan en requirements-optuna.txt y las versiones efectivas constan en summary.json.

```bash
python -m scripts.fetch_nested_result
```

Este comando recupera agregados existentes; no inicia otra búsqueda. Protocolo: experiments/nested_optuna_predictive.json. Workflow: .github/workflows/nested-optuna.yml. Si expira el artifact de entrada, el replay falla sin sustituirlo silenciosamente por otro.
