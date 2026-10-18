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

## Resultado ejecutado

- Código/protocolo publicados antes del cálculo: `71cacc7746c55b439e3826233997a6ba577eef09`.
- Run público estándar: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39084945583 , job25segundos. Check117549500773: https://github.com/joaquinignaciomondaca-code/Idea_3/runs/117549500773 , github-actions, mismo head SHA.
- Originales reauditorados:82 archivos/1730días, sin errores/huecos ni espejo. Dataset extendido idéntico al anterior. Los dos controles SGD10 reproducen sus métricas dentro de1e-12; los archivos anteriores NO se cambian.
- Los12 fits externos batch de cada pasada convergieron y pasaron la comparación con SciPy. Máxima norma final de gradiente3.896e-9. Dos pasadas idénticas en coeficientes/escalas,18 candidatos, selecciones, pronósticos, métricas e intervalos;108fits más24 verificaciones independientes.

### Misma tarea, mismas features, 1.365 etiquetas externas por predictor

| Features | SGD10 anterior | Batch misma L2=0.01 | Batch L2 elegida en validación interna |
|---|---:|---:|---:|
| baseline3, log-loss | 0.695442 | 0.702143 | 0.701299 |
| all24, log-loss | 0.704838 | 0.745267 | 0.721036 |

Menor es mejor. Controles adicionales: p=0.5 obtiene0.693147; prior histórico0.695841; persistencia0.698834. Los dos modelos selected quedan por debajo de ambos baselines probabilísticos. Brier confirma el deterioro: baseline3 selected0.253992 y all24 selected0.262920, frente a0.25 constante.

**Resolver mejor train empeoró el log-loss externo con la misma L2 en ambos conjuntos**: cambio+0.006702 baseline3 y+0.040429 all24. Esto es compatible con regularización implícita por entrenamiento limitado en la receta anterior. No demuestra que early stopping siempre sea superior, ni que el entrenamiento estuviera aritméticamente equivocado; sí descarta atribuir a falta de convergencia, por sí sola, la explicación de malos pronósticos en este diagnóstico.

L2 elegida:2023 baseline3/all24=0.1/0.1;2024=0.1/0.1;2025–2026=0.001/0.01. Se mantienen estas decisiones aunque el test no resulte favorable. No se amplía el grid después de ver elecciones en el extremo.

Los intervalos exploratorios selected−SGD10,selected−p0.5 y selected−prior son positivos con ambos largos de bloque en ambos conjuntos, favoreciendo a las referencias. Por ejemplo selected baseline3−p0.5 tiene delta+0.008152 e IC95%[+0.002768,+0.013604] con14días; all24−p0.5 delta+0.027889 e IC95%[+0.017135,+0.038684]. Se publican también60días y todas las demás comparaciones. No se declaran pruebas confirmatorias ajustadas por multiplicidad o investigación previa.

### Entregables

- `artifacts/converged_classifier/informe.md`: nueve predictores, ambos efectos del optimizador, todos los bloques y doce intervalos exploratorios.
- `artifacts/converged_classifier/summary.json`:18 candidatos/folds,18 auditorías de fit con coeficientes/escalas, todos los resultados y hashes.
- `artifacts/converged_classifier/check_receipt.json`: productor/revisión/Check/hash.
- `python -m scripts.fetch_converged_result`: recupera lo existente vía Checks API sin iniciar nuevas búsquedas; rechaza scope, fuente, selección, convergencia, candidatos/modelos/intervalos omitidos o agregados alterados.
- Registro completo con predicciones y bins de calibración en artifact del workflow, retención7días. Agregados preservados en Git. Los hashes locales de los módulos productores coinciden con los publicados.
- **115 tests locales pasaron**, incluyendo igualdad numérica del control, maduración causal, selección solo con pasado, convergencia, solver independiente, repetición y recepción alterada. No son115 pruebas de utilidad financiera.

Decisión: no promover modelo ni seguir ajustando este mismo histórico hasta obtener verde. La convergencia ahora está verificada, pero no aparece ventaja predictiva en esta tarea/conjunto. Cualquier investigación siguiente necesita una hipótesis informativa distinta y confirmación con datos futuros realmente reservados. No se inicia trading, PnL deUSD20 ni cómputo pagado.
