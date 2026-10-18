# ¿Qué variables aportaron a la predicción?

**FEATURE-ABLATION-001 — experimento ejecutado, solo investigación predictiva retrospectiva.**

Ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39082812342

## Qué se probó

- 24 variables: seis de tendencia, seis de volatilidad, seis de actividad y seis de forma de las velas. Originales oficiales Binance BTCUSDT, no un espejo.
- Ablación con reentrenamiento: quitar una variable/familia y volver a ajustar. Importancia = log-loss SIN esa información − log-loss CON las24. Positivo: quitarla perjudicó; negativo: quitarla ayudó. No es porcentaje ni causalidad.
- Rankings individuales calculados SOLO en dos validaciones internas por bloque; se seleccionan hasta seis variables con delta positivo en ambos folds. Cada selección se congela antes de probar el bloque externo. Si ninguna cumple, solo intercepto.
- Tres bloques externos: 2023, 2024, 2025–26-09-2026. Misma receta para todos: logística SGD fija/adaptativa, tasa0.001, L2=0.01, diez épocas, ventana365, warmup90, scaler mediana/IQR exclusivamente de entrenamiento y clipping[-5,5]. No se optimizaron estos hiperparámetros.
- 390 fits prescritos por pasada, dos pasadas idénticas: 780 fits en total, sin HPO ni elección de semilla. No se trata del presupuesto de 30 trials del estudio anterior.

## Prueba externa: ¿más variables ayudaron?

Menor log-loss/Brier es mejor. Todos tienen 1.365 etiquetas. Comparar baseline3 con all24 dentro de ESTA receta; no mezclar con scores de protocolos anteriores.

| Modelo | Log-loss ↓ | Brier ↓ | Acierto |
|---|---:|---:|---:|
| constant_p0_5 | 0.693147 | 0.250000 | 49.38% |
| persistence | 0.698834 | 0.252830 | 49.67% |
| fixed/baseline3 | 0.695442 | 0.251143 | 49.01% |
| fixed/all24 | 0.704838 | 0.255687 | 47.77% |
| fixed/selected_inner | 0.696032 | 0.251433 | 50.70% |
| adaptive/baseline3 | 0.695360 | 0.251103 | 49.23% |
| adaptive/all24 | 0.701650 | 0.254185 | 48.72% |
| adaptive/selected_inner | 0.696724 | 0.251774 | 50.55% |

### Lectura del resultado

- **Añadir las24 empeoró el log-loss agregado frente a tres señales**, tanto en fijo como adaptativo.
- La selección interna redujo el deterioro respecto de usarlo todo. Eso no demuestra que el subconjunto sea mejor que baseline3 ni que p=0.5.
- **Ningún modelo aprendido superó p=0.5 en log-loss agregado**. No se ha demostrado señal predictiva útil con esta receta.
- Ninguna variable cumplió el requisito en ambos folds en: outer_2024/fixed, outer_2024/adaptive. Se usó solo intercepto; no se forzaron seis variables ni se ocultó el resultado.

## Importancia individual en validaciones internas

Ranking descriptivo por modo: deltas ponderados por observaciones de sus tres validaciones dobles. «Estable» cuenta bloques donde quitarla perjudicó en ambos folds (máximo3). No son tres réplicas independientes ni un ranking universal; las listas globales NO se usaron para reentrenar después de ver externos. Se muestran las24, incluidos los deltas negativos.

### fixed

| Variable | Δ log-loss interno | Estable /3 |
|---|---:|---:|
| close_position_20 | +0.000680 | 2 |
| up_fraction_20 | +0.000414 | 2 |
| return_10 | +0.000286 | 2 |
| range_log | +0.000225 | 1 |
| upper_wick | +0.000166 | 0 |
| return_5 | +0.000162 | 0 |
| quote_relative_20 | +0.000005 | 0 |
| volume_relative_20 | -0.000003 | 0 |
| downside_20 | -0.000013 | 0 |
| return_90 | -0.000152 | 0 |
| intraday_return | -0.000161 | 1 |
| return_1 | -0.000161 | 1 |
| trades_relative_20 | -0.000326 | 0 |
| vol_60 | -0.000327 | 1 |
| atr_20 | -0.000352 | 0 |
| vol_20 | -0.000368 | 1 |
| vol_5 | -0.000370 | 0 |
| taker_imbalance | -0.000372 | 0 |
| return_60 | -0.000415 | 1 |
| trade_size_relative_20 | -0.000751 | 1 |
| return_20 | -0.000844 | 1 |
| lower_wick | -0.000944 | 0 |
| illiquidity_proxy | -0.000988 | 0 |
| open_gap | -0.002424 | 0 |
### adaptive

| Variable | Δ log-loss interno | Estable /3 |
|---|---:|---:|
| close_position_20 | +0.000773 | 1 |
| up_fraction_20 | +0.000617 | 2 |
| return_10 | +0.000230 | 1 |
| return_5 | +0.000190 | 0 |
| range_log | +0.000184 | 1 |
| upper_wick | +0.000152 | 0 |
| quote_relative_20 | -0.000026 | 0 |
| volume_relative_20 | -0.000031 | 0 |
| downside_20 | -0.000059 | 0 |
| return_90 | -0.000111 | 0 |
| return_1 | -0.000178 | 1 |
| intraday_return | -0.000178 | 1 |
| return_60 | -0.000322 | 1 |
| atr_20 | -0.000340 | 0 |
| trades_relative_20 | -0.000357 | 0 |
| vol_20 | -0.000369 | 1 |
| vol_5 | -0.000386 | 0 |
| vol_60 | -0.000386 | 0 |
| taker_imbalance | -0.000622 | 0 |
| return_20 | -0.000727 | 1 |
| trade_size_relative_20 | -0.000736 | 1 |
| illiquidity_proxy | -0.000804 | 0 |
| lower_wick | -0.000812 | 0 |
| open_gap | -0.002351 | 0 |

## Subconjuntos elegidos antes de cada test

| Bloque | Modo | Variables |
|---|---|---|
| outer_2023 | fixed | close_position_20, vol_60, up_fraction_20, return_10, return_60, return_20 |
| outer_2023 | adaptive | close_position_20, up_fraction_20, return_60, return_20 |
| outer_2024 | fixed | Solo intercepto |
| outer_2024 | adaptive | Solo intercepto |
| outer_2025_2026 | fixed | up_fraction_20, trade_size_relative_20, return_1, intraday_return, range_log, return_10 |
| outer_2025_2026 | adaptive | up_fraction_20, trade_size_relative_20, range_log, return_1, intraday_return, vol_20 |

## Ablaciones familiares externas: diagnóstico, no selección

Diferencia de log-loss agregado respecto de all24, con reentrenamiento en ambos casos. Positivo favorece conservar la familia; negativo favorece eliminarla en esta receta y período. Estos resultados NO alimentan el selector.

| Familia eliminada | Δ fijo | Δ adaptativo |
|---|---:|---:|
| Tendencia | -0.002121 | -0.001242 |
| Volatilidad | +0.000466 | +0.000101 |
| Actividad | -0.004633 | -0.002809 |
| Forma de velas | -0.003959 | -0.002065 |

## Todos los resultados externos por bloque

| Bloque | Modelo | n | Log-loss ↓ | Brier ↓ |
|---|---|---:|---:|---:|
| outer_2023 | adaptive/all24 | 365 | 0.708719 | 0.257598 |
| outer_2023 | adaptive/baseline3 | 365 | 0.697043 | 0.251934 |
| outer_2023 | adaptive/selected_inner | 365 | 0.700342 | 0.253541 |
| outer_2023 | adaptive/without_activity | 365 | 0.703696 | 0.255173 |
| outer_2023 | adaptive/without_candles | 365 | 0.703317 | 0.254977 |
| outer_2023 | adaptive/without_trend | 365 | 0.704760 | 0.255738 |
| outer_2023 | adaptive/without_volatility | 365 | 0.713786 | 0.260015 |
| outer_2023 | constant_p0_5 | 365 | 0.693147 | 0.250000 |
| outer_2023 | fixed/all24 | 365 | 0.717954 | 0.261936 |
| outer_2023 | fixed/baseline3 | 365 | 0.697341 | 0.252082 |
| outer_2023 | fixed/selected_inner | 365 | 0.699297 | 0.253027 |
| outer_2023 | fixed/without_activity | 365 | 0.706933 | 0.256704 |
| outer_2023 | fixed/without_candles | 365 | 0.706204 | 0.256367 |
| outer_2023 | fixed/without_trend | 365 | 0.710140 | 0.258330 |
| outer_2023 | fixed/without_volatility | 365 | 0.726960 | 0.266101 |
| outer_2023 | persistence | 365 | 0.694599 | 0.250719 |
| outer_2024 | adaptive/all24 | 366 | 0.694657 | 0.250765 |
| outer_2024 | adaptive/baseline3 | 366 | 0.693982 | 0.250417 |
| outer_2024 | adaptive/selected_inner | 366 | 0.693057 | 0.249955 |
| outer_2024 | adaptive/without_activity | 366 | 0.693091 | 0.249990 |
| outer_2024 | adaptive/without_candles | 366 | 0.694798 | 0.250822 |
| outer_2024 | adaptive/without_trend | 366 | 0.694525 | 0.250697 |
| outer_2024 | adaptive/without_volatility | 366 | 0.695001 | 0.250928 |
| outer_2024 | constant_p0_5 | 366 | 0.693147 | 0.250000 |
| outer_2024 | fixed/all24 | 366 | 0.695734 | 0.251287 |
| outer_2024 | fixed/baseline3 | 366 | 0.694279 | 0.250565 |
| outer_2024 | fixed/selected_inner | 366 | 0.693048 | 0.249950 |
| outer_2024 | fixed/without_activity | 366 | 0.693715 | 0.250288 |
| outer_2024 | fixed/without_candles | 366 | 0.695599 | 0.251222 |
| outer_2024 | fixed/without_trend | 366 | 0.696104 | 0.251472 |
| outer_2024 | fixed/without_volatility | 366 | 0.695180 | 0.251015 |
| outer_2024 | persistence | 366 | 0.693786 | 0.250314 |
| outer_2025_2026 | adaptive/all24 | 634 | 0.701616 | 0.254195 |
| outer_2025_2026 | adaptive/baseline3 | 634 | 0.695186 | 0.251019 |
| outer_2025_2026 | adaptive/selected_inner | 634 | 0.696758 | 0.251806 |
| outer_2025_2026 | adaptive/without_activity | 634 | 0.699365 | 0.253095 |
| outer_2025_2026 | adaptive/without_candles | 634 | 0.700198 | 0.253515 |
| outer_2025_2026 | adaptive/without_trend | 634 | 0.701298 | 0.254040 |
| outer_2025_2026 | adaptive/without_volatility | 634 | 0.698719 | 0.252760 |
| outer_2025_2026 | constant_p0_5 | 634 | 0.693147 | 0.250000 |
| outer_2025_2026 | fixed/all24 | 634 | 0.702544 | 0.254628 |
| outer_2025_2026 | fixed/baseline3 | 634 | 0.695020 | 0.250936 |
| outer_2025_2026 | fixed/selected_inner | 634 | 0.695874 | 0.251371 |
| outer_2025_2026 | fixed/without_activity | 634 | 0.700080 | 0.253436 |
| outer_2025_2026 | fixed/without_candles | 634 | 0.700863 | 0.253833 |
| outer_2025_2026 | fixed/without_trend | 634 | 0.702261 | 0.254495 |
| outer_2025_2026 | fixed/without_volatility | 634 | 0.698682 | 0.252734 |
| outer_2025_2026 | persistence | 634 | 0.704186 | 0.255497 |

## Límites y trazabilidad

- Un ranking de un modelo débil no identifica automáticamente una señal útil. Las variables correlacionadas pueden sustituirse y los efectos individuales no se suman.
- El histórico BTC ya estaba inspeccionado. Externo significa excluido del selector de ese bloque, no holdout virgen ni publicación prospectiva. Sin pruebas de significancia ni disponibilidad histórica certificada.
- No se promueve un ganador, se cambia la selección ni se amplía la búsqueda después de ver los resultados. El estado success del workflow solo confirma ejecución y validaciones.
- No se calcularon rentabilidad de USD20, Sharpe ni costos operativos. Actividad/iliquidez son proxies de velas, no spread ejecutable. No Laya, evolución ni trading real.
- Reauditoría: 82 archivos, 1730 días; quote volume, trades y taker validados adicionalmente. Dos pasadas iguales en rankings, selecciones, escalas, pesos iniciales y predicciones. Python 3.12.3, NumPy 2.2.6.
- summary.json conserva las24 ablaciones individuales y cuatro familiares de cada modo/bloque y todos los scores externos. Los registros completos, escalas, pesos y pronósticos están en el artifact del workflow, retención7días. Agregados preservados en Git.

## Fuentes, licencia y reproducción

Binance Vision: https://data.binance.vision/ . Formato oficial Klines: https://github.com/binance/binance-public-data/tree/d571690eb66760763b0bd6e27e8cd35603c7e244 . Términos CC BY-NC-SA4.0 salvo designación distinta; solo investigación no comercial. Informe derivado bajo CC BY-NC-SA4.0. Términos/atribución en el artifact; sin aval del proveedor.

Protocolo: experiments/feature_ablation.json. Fórmulas y limitaciones: docs/investigacion/14_variables_y_ablacion.md.

```bash
python -m scripts.fetch_feature_result
```

Solo recupera agregados existentes mediante Checks API; no inicia nuevos fits ni requiere descargar artifact storage.
