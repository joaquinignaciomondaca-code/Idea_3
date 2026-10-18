# Auditoría numérica y adaptación semanal — resultados

Ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39083857802

**Dos tareas separadas. No se modificó ni se volvió a puntuar el test del experimento anterior. No PnL ni aprobación para operar.**

## 1. Hallazgo numérico: diez épocas no resolvían el objetivo de train

Se reauditaron los originales y se recuperaron los pesos del artifact del experimento anterior. Las seis reconstrucciones iniciales coinciden dentro de la tolerancia1e-10; fijo/adaptativo compartían ese estado. Se agregó el primer ajuste interno, con88 ejemplos y25 coeficientes, como diagnóstico.

Gradiente analítico, diferencias finitas y pasos de producción concuerdan. Newton y SciPy L-BFGS-B (con derivadas numéricas y otra expresión estable del objetivo) llegan a soluciones compatibles. No se encontró un error de signo/normalización en estas comprobaciones; no es una prueba de ausencia de cualquier bug.

| Caso | n train | Parámetros | J en época10 | J óptimo referencia | Gap | Norma gradiente época10 |
|---|---:|---:|---:|---:|---:|---:|
| outer_2023/baseline3 | 272 | 4 | 0.684109 | 0.679364 | 0.004745 | 0.032850 |
| outer_2023/all24 | 272 | 25 | 0.668114 | 0.656295 | 0.011819 | 0.027068 |
| outer_2024/baseline3 | 365 | 4 | 0.692756 | 0.692536 | 0.000220 | 0.007824 |
| outer_2024/all24 | 365 | 25 | 0.684289 | 0.676571 | 0.007718 | 0.015286 |
| outer_2025_2026/baseline3 | 365 | 4 | 0.688697 | 0.686559 | 0.002138 | 0.015055 |
| outer_2025_2026/all24 | 365 | 25 | 0.678671 | 0.670271 | 0.008400 | 0.015731 |
| first_inner_2022/all24 | 88 | 25 | 0.671525 | 0.628054 | 0.043471 | 0.086508 |

Error máximo del gradiente frente a diferencias finitas: 1.361e-10. Diferencia máxima de coeficientes entre solvers: 3.553e-07. En ningún caso se activó el clipping de logits>=35.

**Los siete casos no cumplen la tolerancia de convergencia en época10.** El objetivo de la tabla es log-loss de ENTRENAMIENTO más L2/2, no el log-loss externo. Las trayectorias0/1/10/100/1000 completas se conservan en audit_summary.json. Con paso constante, SGD puede quedar cerca del óptimo sin llegar a su tolerancia; aumentar épocas a ciegas tampoco certifica convergencia.

Esto identifica una limitación del procedimiento: no habíamos verificado su calidad como solución del objetivo declarado. Pero parar temprano puede regularizar implícitamente. **No demuestra que resolver mejor train mejore test, ni explica causalmente los malos resultados históricos.** No se sustituyen sus scores por los del óptimo.

## 2. Adaptación parcial: magnitud de retorno semanal

Inspirada en el componente de momentum temporal semanal de Liu/Tsyvinski, NBER24877(2018). No es réplica exacta del artículo, no CTREND transversal y no incluye atención/red ni sus datos originales.

- Señal al cierre UTC del domingo. Target: close[t+8]/open[t+2]−1, referencia de siete sesiones de martes a lunes tras un día completo intermedio. No fill garantizado.
- BTCUSDT, no retorno exacto USD ni exceso sobre tasa libre de riesgo. Features: momentum7/28/84 y volatilidad28. Mediana/IQR de train, clipping[-5,5].
- OLS momentum7 y ridge4 con alpha1 fijo, ambos por solución cerrada/lstsq, no SGD. Seis ajustes por pasada, dos pasadas idénticas=12 fits, sin HPO ni selección de horizonte/semilla/umbral.
- Baselines: retorno0 y media histórica solo de etiquetas maduras de train. Ventanas expansivas con92/144/196 semanas de entrenamiento; modelos congelados por año2024/2025/2026.
- Métrica primaria MSE; R²_OOS expresa mejora relativa frente a media histórica. No equivale a rentabilidad. Todas las métricas/cohortes y los dos largos de bootstrap se publican.

### Agregado externo: 141 semanas (52/52/37 por año)

| Modelo | MSE ↓ | MAE ↓ | R² OOS vs media | Dirección |
|---|---:|---:|---:|---:|
| historical_mean | 0.004980435 | 0.052004 | +0.0000% | 49.65% |
| zero | 0.004975450 | 0.051659 | +0.1001% | 50.35% |
| ols_momentum7 | 0.004997363 | 0.051918 | -0.3399% | 47.52% |
| ridge4 | 0.004975951 | 0.051952 | +0.0900% | 48.23% |

MSE se mide en retorno fraccional al cuadrado y MAE en retorno fraccional. Por ejemplo MAE0.052 significa error absoluto medio de5.2 puntos porcentuales, no ganancia5.2%. Retorno0 tiene dirección siempre «no positivo», no una moneda aleatoria.

### Incertidumbre exploratoria emparejada

Diferencia de pérdidas cuadráticas modelo−media histórica; negativo favorece modelo. Bootstrap circular dentro de cada año,2000réplicas,seed1701, percentiles95%. No se corrige multiplicidad ni investigación previa. Ambos largos de bloque se reportan; no son ensayos independientes.

| Modelo | Bloque semanas | Diferencia media | IC95% inferior | IC95% superior |
|---|---:|---:|---:|---:|
| ols_momentum7 | 4 | +0.00001693 | -0.00003579 | +0.00007486 |
| ols_momentum7 | 12 | +0.00001693 | -0.00003942 | +0.00008249 |
| ridge4 | 4 | -0.00000448 | -0.00007753 | +0.00006063 |
| ridge4 | 12 | -0.00000448 | -0.00007118 | +0.00006472 |
| zero | 4 | -0.00000498 | -0.00011765 | +0.00010880 |
| zero | 12 | -0.00000498 | -0.00010387 | +0.00009465 |

### Todos los bloques

| Año | Modelo | n | MSE ↓ | R² OOS vs media |
|---|---|---:|---:|---:|
| 2024 | historical_mean | 52 | 0.007718161 | +0.0000% |
| 2024 | ols_momentum7 | 52 | 0.007750651 | -0.4210% |
| 2024 | ridge4 | 52 | 0.007665724 | +0.6794% |
| 2024 | zero | 52 | 0.007797154 | -1.0235% |
| 2025 | historical_mean | 52 | 0.002689339 | +0.0000% |
| 2025 | ols_momentum7 | 52 | 0.002704476 | -0.5628% |
| 2025 | ridge4 | 52 | 0.002736219 | -1.7432% |
| 2025 | zero | 52 | 0.002621748 | +2.5133% |
| 2026 | historical_mean | 37 | 0.004352736 | +0.0000% |
| 2026 | ols_momentum7 | 37 | 0.004350313 | +0.0557% |
| 2026 | ridge4 | 37 | 0.004343461 | +0.2131% |
| 2026 | zero | 37 | 0.004317717 | +0.8045% |

## Lectura y siguiente decisión

- Ridge tiene R² OOS +0.0900% frente a media histórica; OLS -0.3399%. Son porcentajes de reducción de error, NO retorno de una inversión.
- Predecir siempre retorno0 obtiene MSE ligeramente mejor que ridge. Una pequeña mejora sobre la media histórica no basta para demostrar señal útil.
- Los intervalos de ambos modelos incluyen0 con ambos largos de bloque: esta exploración no establece una ventaja estadística sólida.
- No se promueve ganador, se cambian métricas ni se reoptimiza alpha/épocas después de ver estos resultados. Para un próximo clasificador, usar solver controlado o justificar explícitamente early stopping dentro de validación, no asumir que diez épocas resuelven el objetivo.
- La adaptación semanal responde otra pregunta. No rescata el experimento de dirección diaria ni constituye una réplica confirmada del paper.
- El histórico ya inspeccionado continúa siendo exploratorio. Confirmación requiere observaciones futuras realmente reservadas. Costos, filtros, liquidez y fills aplicables siguen pendientes: no inferir utilidad paraUSD20.

## Integridad y reproducción

Protocolos/código publicados antes del cálculo. Reauditoría82 archivos/1730días, sin espejo. Dos Checks separados, mismo commit productor; sus recibos y hashes están en check_receipts.json. La auditoría usa solo train; la adaptación tiene dos pasadas idénticas en fits, predicciones, métricas e intervalos. Success significa cálculo validado, no éxito financiero.

```bash
python -m scripts.fetch_numerical_review
```

Recupera agregados existentes por Checks API; no inicia otro runner ni instala paquetes. Audit_summary.json conserva los controles/trajectorias y weekly_summary.json todos los resultados semanales. Pronósticos semanales completos en el artifact, retención7días. Protocolo y matriz de adaptación: docs/investigacion/16_auditoria_y_adaptacion_semanal.md.

Fuente: Binance Vision https://data.binance.vision/; CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial. Informes derivados bajo CC BY-NC-SA4.0. Términos/atribución en el artifact; sin aval del proveedor. No se ejecutaron Laya, población evolutiva, órdenes ni servicios de inferencia pagados.
