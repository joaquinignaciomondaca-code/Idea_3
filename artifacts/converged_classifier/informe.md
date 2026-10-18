# Clasificador con convergencia controlada — resultados

Ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39084945583

**Comparación retrospectiva controlada. No trading, PnL ni holdout históricamente virgen.**

## Diseño

- Mismos originales BTCUSDT, etiqueta close[i+2]>open[i+2], conjuntos baseline3/all24 y ventanas que FEATURE-ABLATION-001. Warmup90, train365 maduro, escala mediana/IQR de train y clipping[-5,5]. Modelos fijos, sin updates adaptativos.
- SGD10 lr0.001/L2=0.01 reproduce los controles anteriores dentro de1e-12. Batch con MISMA L2=0.01 aísla el efecto de convergencia. Batch seleccionado cambia solamente L2 con validación interna.
- Objetivo batch: log-loss medio+alpha/2*sum(pesos sin intercepto²). Newton/Armijo tolerancia gradiente1e-8, máximo100iteraciones; cada ajuste externo batch verificado con SciPy independiente.
- Grid L2=0.001/0.01/0.1:18 candidatos en seis estudios (dos matrices×tres bloques),36 fits internos+18externos por pasada. Dos pasadas idénticas=108fits, más24 verificaciones SciPy; no búsqueda de épocas, horizonte, semillas ni umbrales.
- Prior histórico suavizado: (subidas+1)/(n+2) SOLO sobre las mismas etiquetas maduras del train. También p=0.5 y persistencia0.55/0.45.

## Todos los resultados agregados externos

Cada predictor tiene1.365 etiquetas, 2023–26-09-2026. Menor log-loss/Brier es mejor.

| Predictor | Log-loss ↓ | Brier ↓ | Acierto |
|---|---:|---:|---:|
| constant_p0_5 | 0.693147 | 0.250000 | 49.38% |
| historical_prior | 0.695841 | 0.251340 | 50.40% |
| persistence | 0.698834 | 0.252830 | 49.67% |
| baseline3/sgd10 | 0.695442 | 0.251143 | 49.01% |
| baseline3/converged_same_alpha | 0.702143 | 0.254383 | 47.99% |
| baseline3/converged_selected | 0.701299 | 0.253992 | 48.21% |
| all24/sgd10 | 0.704838 | 0.255687 | 47.77% |
| all24/converged_same_alpha | 0.745267 | 0.271946 | 49.74% |
| all24/converged_selected | 0.721036 | 0.262920 | 49.01% |

## Efecto aislado del optimizador

- baseline3: SGD10 0.695442 → batch misma L2 0.702143; cambio +0.006702 (positivo=peor).
- all24: SGD10 0.704838 → batch misma L2 0.745267; cambio +0.040429 (positivo=peor).
**Converger mejor el objetivo de train empeoró el score externo en ambos conjuntos con la misma L2.** La falta de convergencia no era evidencia de que resolver mejor train fuera a mejorar test; early stopping podía regularizar implícitamente.
**Los dos procedimientos con L2 seleccionada internamente siguen sin superar p=0.5 en log-loss agregado.** No se ha demostrado señal útil; no se promueve ganador.

## Parámetros elegidos sin usar test

| Bloque | Features | L2 elegida |
|---|---|---:|
| outer_2023 | baseline3 | 0.1 |
| outer_2023 | all24 | 0.1 |
| outer_2024 | baseline3 | 0.1 |
| outer_2024 | all24 | 0.1 |
| outer_2025_2026 | baseline3 | 0.001 |
| outer_2025_2026 | all24 | 0.01 |

Los18 candidatos completos y sus pérdidas por fold están en summary.json. No se amplía el grid después de ver parámetros o externos.

## Gradientes finales de los ajustes externos

| Bloque | Modelo | Gradiente infinito | Diferencia coef. vs SciPy |
|---|---|---:|---:|
| outer_2023 | baseline3/converged_same_alpha | 2.652e-12 | 1.548e-10 |
| outer_2023 | baseline3/converged_selected | 1.311e-14 | 2.964e-09 |
| outer_2023 | all24/converged_same_alpha | 3.393e-15 | 2.142e-07 |
| outer_2023 | all24/converged_selected | 1.192e-10 | 1.937e-08 |
| outer_2024 | baseline3/converged_same_alpha | 6.976e-11 | 3.511e-09 |
| outer_2024 | baseline3/converged_selected | 9.778e-13 | 3.185e-11 |
| outer_2024 | all24/converged_same_alpha | 7.109e-10 | 3.549e-07 |
| outer_2024 | all24/converged_selected | 2.071e-12 | 1.565e-08 |
| outer_2025_2026 | baseline3/converged_same_alpha | 1.278e-12 | 2.151e-09 |
| outer_2025_2026 | baseline3/converged_selected | 4.076e-12 | 7.291e-09 |
| outer_2025_2026 | all24/converged_same_alpha | 3.896e-09 | 2.480e-07 |
| outer_2025_2026 | all24/converged_selected | 3.896e-09 | 2.480e-07 |

## Incertidumbre exploratoria

Diferencias emparejadas de log-loss selected−referencia; negativo favorece selected. Bootstrap circular dentro de cada bloque externo,2000réplicas,seed1701, bloques14/60días, percentiles95%. Sin corrección por multiplicidad/investigación previa; no se elige modelo ni largo por este resultado.

| Selected | Referencia | Bloque días | Δ medio | Inferior95% | Superior95% |
|---|---|---:|---:|---:|---:|
| all24/converged_selected | all24/sgd10 | 14 | +0.016198 | +0.009638 | +0.022933 |
| all24/converged_selected | all24/sgd10 | 60 | +0.016198 | +0.009053 | +0.023594 |
| all24/converged_selected | constant_p0_5 | 14 | +0.027889 | +0.017135 | +0.038684 |
| all24/converged_selected | constant_p0_5 | 60 | +0.027889 | +0.016990 | +0.040197 |
| all24/converged_selected | historical_prior | 14 | +0.025195 | +0.015983 | +0.034964 |
| all24/converged_selected | historical_prior | 60 | +0.025195 | +0.016012 | +0.035477 |
| baseline3/converged_selected | baseline3/sgd10 | 14 | +0.005858 | +0.002747 | +0.009057 |
| baseline3/converged_selected | baseline3/sgd10 | 60 | +0.005858 | +0.002988 | +0.008709 |
| baseline3/converged_selected | constant_p0_5 | 14 | +0.008152 | +0.002768 | +0.013604 |
| baseline3/converged_selected | constant_p0_5 | 60 | +0.008152 | +0.002954 | +0.013346 |
| baseline3/converged_selected | historical_prior | 14 | +0.005458 | +0.001319 | +0.009622 |
| baseline3/converged_selected | historical_prior | 60 | +0.005458 | +0.002392 | +0.008400 |

## Todos los bloques externos

| Bloque | Modelo | n | Log-loss ↓ | Brier ↓ |
|---|---|---:|---:|---:|
| outer_2023 | all24/converged_same_alpha | 365 | 0.821039 | 0.300570 |
| outer_2023 | all24/converged_selected | 365 | 0.747950 | 0.274922 |
| outer_2023 | all24/sgd10 | 365 | 0.717954 | 0.261936 |
| outer_2023 | baseline3/converged_same_alpha | 365 | 0.710296 | 0.258268 |
| outer_2023 | baseline3/converged_selected | 365 | 0.707682 | 0.257109 |
| outer_2023 | baseline3/sgd10 | 365 | 0.697341 | 0.252082 |
| outer_2023 | constant_p0_5 | 365 | 0.693147 | 0.250000 |
| outer_2023 | historical_prior | 365 | 0.700978 | 0.253890 |
| outer_2023 | persistence | 365 | 0.694599 | 0.250719 |
| outer_2024 | all24/converged_same_alpha | 366 | 0.717210 | 0.261335 |
| outer_2024 | all24/converged_selected | 366 | 0.699728 | 0.253250 |
| outer_2024 | all24/sgd10 | 366 | 0.695734 | 0.251287 |
| outer_2024 | baseline3/converged_same_alpha | 366 | 0.697370 | 0.252106 |
| outer_2024 | baseline3/converged_selected | 366 | 0.695347 | 0.251099 |
| outer_2024 | baseline3/sgd10 | 366 | 0.694279 | 0.250565 |
| outer_2024 | constant_p0_5 | 366 | 0.693147 | 0.250000 |
| outer_2024 | historical_prior | 366 | 0.693017 | 0.249935 |
| outer_2024 | persistence | 366 | 0.693786 | 0.250314 |
| outer_2025_2026 | all24/converged_same_alpha | 634 | 0.717842 | 0.261593 |
| outer_2025_2026 | all24/converged_selected | 634 | 0.717842 | 0.261593 |
| outer_2025_2026 | all24/sgd10 | 634 | 0.702544 | 0.254628 |
| outer_2025_2026 | baseline3/converged_same_alpha | 634 | 0.700205 | 0.253461 |
| outer_2025_2026 | baseline3/converged_selected | 634 | 0.701061 | 0.253867 |
| outer_2025_2026 | baseline3/sgd10 | 634 | 0.695020 | 0.250936 |
| outer_2025_2026 | constant_p0_5 | 634 | 0.693147 | 0.250000 |
| outer_2025_2026 | historical_prior | 634 | 0.694514 | 0.250683 |
| outer_2025_2026 | persistence | 634 | 0.704186 | 0.255497 |

## Alcance y trazabilidad

- Se mantienen los resultados anteriores sin sobrescribirlos. El comparador SGD se recalcula para verificar la comparación controlada, no para sustituir el informe previo.
- Todo BTC ya fue inspeccionado. Excluir test del selector no borra decisiones humanas previas. Los intervalos no certifican generalización ni disponibilidad histórica de datos.
- No se atribuye causalidad general a un experimento: el efecto observado del optimizador es condicional a estos datos, etiqueta, scaler, L2 y ventana. Más optimización no fabrica información.
- No se alteran métricas para encontrar un resultado favorable, se elige un ganador por externos ni se pasa a una política deUSD20 sin costos/filtros/fills comprobados. Sin Laya, evolución, órdenes ni inferencia pagada.
- Reauditoría82 originales/1730días, fuente y control SGD verificados. Python3.12.3, NumPy2.2.6, SciPy1.15.3. Dos pasadas iguales en fits, candidatos, selecciones, predicciones, métricas e intervalos.
- Resultados completos y pronósticos en artifact, retención7días; agregados, coeficientes/escalas y recibo se preservan en Git. Success significa controles/cálculo completados, no ventaja financiera.

Protocolo: experiments/converged_classifier.json; documentación: docs/investigacion/17_clasificador_con_convergencia.md.

```bash
python -m scripts.fetch_converged_result
```

Recupera agregados existentes por Checks API, sin nuevos fits ni descargas manuales. Fuente Binance Vision https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial. Informe derivado bajo CC BY-NC-SA4.0; términos/atribución en el artifact, sin aval del proveedor.
