# 14 — Variables predictivas y ablación con reentrenamiento

## Plan previo a resultados — FEATURE-ABLATION-001

Se amplía de tres señales a **24 variables**, agrupadas en cuatro familias. No se modifican los protocolos anteriores ni se supone que añadir indicadores mejore el modelo. Se usan las mismas velas oficiales BTCUSDT 1d 2022-01-01–2026-09-26, recuperadas en su adquisición original; no un espejo ni datos sintéticos como evidencia financiera.

### Variables y disponibilidad

Todas las cantidades de la fila i se conocen solo después del cierre de esa sesión. El pronóstico apunta a close[i+2]>open[i+2]. Las transformaciones usan la sesión actual y el pasado, no el futuro. Warmup común de 90 retornos para todos los modelos, incluso el baseline de tres señales.

| Familia | Seis variables |
|---|---|
| Tendencia | ln(close[i]/close[i-k]) con k=1,5,10,20,60,90 |
| Volatilidad | Desvío poblacional de retornos logarítmicos en 5/20/60 sesiones; ln(high/low) actual; media del true range de 20 sesiones dividida por close actual; raíz de la media de retornos negativos al cuadrado en 20 sesiones |
| Actividad | ln(volumen base/media20), ln(volumen cotizado/media20), ln(número operaciones/media20), ln(tamaño cotizado medio de operación/media20 de ese tamaño), 2*taker_buy_quote/quote_volume−1, abs(retorno1)/(quote_volume/1e6) |
| Velas | ln(close/open), mecha superior/rango, mecha inferior/rango, ln(open/close previo), fracción de velas alcistas en 20 sesiones, posición de close entre mínimo low y máximo high de 20 sesiones |

Mechas de una vela sin rango valen cero; una posición sin rango de 20 sesiones vale 0.5. Una actividad ausente/no positiva se rechaza, no se rellena silenciosamente. La última medida de actividad es un **proxy de iliquidez**, no spread observado ni costo de ejecución. Taker buy es actividad agregada del mercado, no identificación de inversores institucionales.

El paquete antiguo normalizado conservaba solo open/close: este experimento vuelve a leer los ZIP originales y valida también high/low/volume, quote volume, número de operaciones y volúmenes taker. La semántica de las columnas procede del formato oficial Binance Klines, documentado en el repositorio del productor: https://github.com/binance/binance-public-data/tree/d571690eb66760763b0bd6e27e8cd35603c7e244 . Los timestamps de 2025+ en microsegundos se normalizan a fechas UTC.

### Modelo, escala y controles

Se mantienen dos versiones de regresión logística SGD: fija y adaptativa; no son dos algoritmos de ML distintos. Learning rate=0.001, L2=0.01, diez épocas y últimos 365 ejemplos maduros (o los realmente disponibles), con mínimo60. Es una receta declarada influida por investigación previa, no un óptimo demostrado. No hay Optuna ni nuevos hiperparámetros elegidos por test.

Cada ajuste aprende medianas y rangos intercuartílicos SOLO de sus features de entrenamiento, divide por IQR (si es cero se reemplaza por1), recorta [-5,5] y añade intercepto. El intercepto no se regulariza. Scaler congelado durante el bloque; el adaptativo solo actualiza pesos tras madurar cada pronóstico. Las etiquetas j+2 posteriores al cutoff quedan fuera del entrenamiento.

Comparadores externos por cada modo:

1. Las 24 variables.
2. Las tres señales base: retorno1, retorno5 y volatilidad20, pero con el MISMO warmup, scaler y receta de este experimento.
3. Subconjunto seleccionado en validaciones internas.
4. Cuatro modelos adicionales, quitando por separado cada familia completa y reentrenando.

También p=0.5 y persistencia 0.55/0.45. Estos scores nuevos no son una comparación controlada con protocolos previos que usaban otra escala, warmup o tasa.

### Importancia y selección temporal

Se conservan los tres bloques externos 2023,2024,2025–26-09-2026. Cada bloque usa dos validaciones internas Q3/Q4 del año anterior, terminadas antes de su primer forecast cutoff. El selector recibe un prefijo separado hasta test_start−2.

```text
Importancia = log_loss_validación(modelo reentrenado SIN variable/familia)
              − log_loss_validación(modelo CON las24)
```

Un valor positivo significa que eliminarla perjudicó esta receta; uno negativo, que eliminarla ayudó. No es un porcentaje, un coeficiente del modelo ni causalidad.

Se evalúan TODAS las 24 eliminaciones individuales y las cuatro familiares. Se ponderan las pérdidas por observaciones. Para el subconjunto se admiten hasta seis variables con importancia positiva en AMBOS folds internos, ordenadas por delta ponderado y luego alfabéticamente. Si ninguna cumple, se usa solo el intercepto. No se hace selección iterativa ni se presupone que juntar seis variables útiles individualmente conserve sus aportes.

Ambos subconjuntos se congelan antes de evaluar cualquiera en el bloque externo. Las ablaciones externas por familia son diagnósticos posteriores: nunca alimentan esta selección. No se promueve familia, modelo o período por score externo.

### Presupuesto, repetición y límites

Cada pasada realiza 390 fits: 3 bloques × 2 modos × (2 fits internos completos +24×2 ablaciones individuales +4×2 ablaciones familiares +7 fits externos). Se repite todo dos veces: **780 fits prescritos**, no 30 trials nuevos ni una búsqueda abierta. No se descartan pruebas desfavorables.

Se conservarán todos los rankings internos, subconjuntos elegidos, resultados externos, pronósticos originales, escalas y pesos iniciales externos, hashes de código/datos/protocolo. Dos pasadas deben reproducir todos esos resultados exactamente. Los registros no son una prueba externa de publicación de pronósticos históricos.

El histórico ya estaba inspeccionado: esta exclusión temporal no es un holdout virgen. Las señales correlacionadas pueden sustituirse. Una importancia pequeña en un modelo malo no prueba que la información sea inútil con otros modelos. No se estiman p-values ni se tratan folds/modos como réplicas independientes. No hay PnL de USD20, Sharpe, órdenes, costos verificados, Laya ni evolución.

Datos y productos derivados: Binance Vision, https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta; solo investigación no comercial. Términos/atribución acompañan al artifact, siete días de retención para registros completos y agregados preservados en Git. Sin aval del proveedor.
