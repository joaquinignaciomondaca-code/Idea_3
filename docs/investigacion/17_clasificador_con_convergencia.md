# 17 — Comparación controlada de convergencia del clasificador

## Preregistro CONVERGED-CLASSIFIER-001

Objetivo: separar el efecto de resolver mejor el objetivo batch del efecto de cambiar datos, etiquetas o variables. No se modifican los experimentos cerrados ni se promete que converger mejore la generalización.

Fuente: el mismo artifact oficial BTCUSDT 1d 2022-01-01–2026-09-26. Se reaudita y exige identidad del hash de datos extendidos del estudio FEATURE-ABLATION-001. No espejo. Etiqueta: close[i+2]>open[i+2], ties=no sube. Los mismos bloques externos2023/2024/2025–2026-09-26 y dos validaciones internas Q3/Q4 anteriores, sin datos posteriores al primer cutoff externo.

### Comparación justa

- Dos matrices de features EXACTAS: baseline3 y all24, mismo orden, warmup90, ventana365 de ejemplos maduros, mínimo60. No quitar redundancias en este experimento: hacerlo mezclaría causas.
- Mediana/IQR de train, IQR0->1 y clipping[-5,5], congelados durante el bloque. Solo modelos FIJOS, sin updates adaptativos.
- Tres ajustes por matriz: SGD10 con learning rate0.001/L2=0.01 como control anterior; batch convergido con la MISMA L2=0.01 para aislar optimizador; batch con L2 seleccionada únicamente en validaciones internas.
- Objetivo batch: media del log-loss + alpha/2*sum(coeficientes sin intercepto²). No confundir media con suma ni alpha con C de otra librería.
- Newton/Armijo con máximo100 iteraciones, norma gradiente infinito<1e-8. Tolerancia de redondeo4*epsilon en comparación del objetivo de line search, sin saltar el control de gradiente. Abortamos si gradiente final>1e-7 o clipping de logits de train>=35.
- Los12 ajustes externos batch por pasada se verifican con SciPy L-BFGS-B y derivadas numéricas independientes: diferencia objetivo<=1e-9 y coeficientes<=1e-4. Si falla uno, abortar, no eliminarlo del reporte.
- Todos los controles SGD10 deben reproducir el log-loss/Brier/acierto agregado anterior dentro de1e-12. El experimento anterior conserva sus archivos originales.

La tolerancia numérica se fijó después de pruebas exclusivamente FICTICIAS y antes de métricas de mercado. Esas pruebas detectaron estancamiento de Armijo al exigir1e-10 sin permitir redondeo en el objetivo y diferencias de últimas cifras por disposición de arrays. Se corrigió en un solver NUEVO, sin cambiar el módulo de auditoría anterior ni relajar requisitos después de observar scores externos.

### Selección y presupuesto

Grid fijo alpha=[0.001,0.01,0.1], tres candidatos por matriz y bloque externo. Objetivo de selección: log-loss medio ponderado por número de observaciones de los dos folds internos; empate por alpha menor. Ambos parámetros se congelan antes de medir ningún modelo externo en ese bloque. No elección global entre matrices o modos mirando test.

18 candidatos ×2 folds=36 fits internos, más18 fits externos=54 por pasada. Dos pasadas idénticas=108 fits más24 verificaciones SciPy externas. No Optuna, búsqueda de semillas, épocas, umbrales o horizontes. Todas las selecciones, coeficientes, escalas, gradientes, scores y pronósticos deben repetirse exactamente entre pasadas en el mismo entorno.

### Baselines y evaluación

Nueve predictores: seis modelos anteriores más p=0.5, persistencia0.55/0.45 y prior histórico suavizado (n_subidas+1)/(n+2), calculado SOLO en las mismas etiquetas maduras de train. No se estima la frecuencia usando todo el test.

Métrica primaria log-loss. Secundarias Brier y acierto, sin escoger retrospectivamente la favorable. Se publican todos los bloques y agregados ponderados por observaciones.

Para selected vs SGD10, p=0.5 y prior histórico: diferencia emparejada de log-loss, bootstrap circular dentro de cada bloque externo, largos14/60días,2000réplicas, semilla1701 y percentiles95%. Ambos largos reportados. Intervalos descriptivos, no corrección de multiplicidad ni de investigación anterior; no se consideran folds como ensayos independientes ni se elige un ganador por intervalos.

### Límites y reproducibilidad

El BTC histórico ya fue inspeccionado. Esto es exclusión temporal algorítmica y diagnóstico retrospectivo, no holdout virgen ni confirmación futura. Mejor train podría empeorar test y early stopping podría regularizar implícitamente. No se pasa a PnL, USD20, costos, filtros o fills no verificados, órdenes, shorts, Laya, población ni inferencia pagada.

Protocolo: `experiments/converged_classifier.json`. Código nuevo: `microtrade/converged_classifier.py`. Runner: `scripts/run_converged_classifier.py`. Workflow público estándar con límite10minutos; dependencias CPU fijadas en `requirements-audit.txt`. Resultados completos en artifact con retención7días, agregados en Git y Checks API. Si expira el original, fallar sin sustituirlo.

Binance Vision, https://data.binance.vision/: términos CC BY-NC-SA4.0 salvo designación distinta, solo investigación no comercial. Informes derivados bajo CC BY-NC-SA4.0. Términos/atribución acompañan al artifact; no hay aprobación del proveedor.
