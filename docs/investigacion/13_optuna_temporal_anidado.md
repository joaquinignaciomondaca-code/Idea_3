# 13 — Función objetivo y primera optimización temporal anidada

Fecha local de especificación y ejecución: 17-10-2026 (Santiago). Finalización UTC: 18-10-2026 00:03:35Z.

## Pregunta y decisión

¿Mejora el predictor fijo/adaptativo si se ajustan tasa de aprendizaje, regularización y cantidad de historia, sin usar las puntuaciones externas para escoger parámetros?

Se ejecutó **NESTED-OPTUNA-PREDICTIVE-001**. No se optimizó dinero, Sharpe ni riesgo de una política operativa: todavía no hay un backtest económico con costos/filtros pertinentes verificados.

Para cada configuración θ se minimiza:

```text
LL_k(θ) = -mean(y*ln(p) + (1-y)*ln(1-p)) en validación interna k
J(θ) = (n_1*LL_1(θ) + n_2*LL_2(θ))/(n_1+n_2)
```

El log-loss usa la probabilidad emitida antes de observar la etiqueta. L2 afecta el entrenamiento de los coeficientes, excepto el intercepto; no se suma una penalización arbitraria al score de validación. La dispersión de los dos scores internos se registra, pero no se eligió un lambda después de mirar resultados. Brier, acierto y calibración son diagnósticos secundarios.

## Congelación, presupuesto y selección

- Protocolo/código publicados en **df5658a493e1224426dcf62af3d77956658bf53f**, antes de iniciar el cálculo. El hash del protocolo y los hashes de los módulos efectivos están en el agregado recibido.
- Tres bloques externos: 2023, 2024 y 2025–26-09-2026. En cada uno, fijo y adaptativo tienen estudios separados de cinco intentos: **30 intentos nuevos totales**, no 300 ni 30 por fold.
- Dos validaciones internas: Q3 y Q4 del año anterior, con Q4 terminado el 30 de diciembre. La selección ocurre en el primer cutoff externo, dos días antes de su primera etiqueta; no se entrega al optimizador el resto de las barras.
- TPE de Optuna 4.5.0: dos trials iniciales por estudio, luego tres guiados; semillas 1701–1706, una tarea a la vez y sin pruning. No se ha demostrado que cinco intentos basten o que TPE venza a búsqueda aleatoria.
- Espacio fijado: learning rate 0.001–0.05 y L2 1e-5–0.1, ambos logarítmicos; ventanas 90/180/365 ejemplos elegibles. Entrenamiento cronológico de diez épocas, mínimo 60 ejemplos.
- Etiqueta: close[i+2] > open[i+2]. Cada fit excluye j si j+2 es posterior al cutoff. El adaptativo actualiza una vez al madurar el pronóstico, usando las features guardadas y la probabilidad originalmente emitida para puntuar.
- Ambos modos se seleccionan antes de evaluar cualquiera sobre el bloque externo. No se escoge entre fijo/adaptativo por sus scores externos. Los parámetros se mantienen durante todo ese bloque; no hay reoptimización en 2026.
- El control sin ajustar usa el mismo reinicio externo y entrenamiento con ventana 365, learning rate 0.02 y L2=0. No es el control del replay anterior con arrastre de pesos a través de épocas.

Se repitió todo con las mismas semillas: 60 evaluaciones del objetivo en total, cada una con dos folds internos. La repetición no añadió otros candidatos entre los que escoger; verificó igualdad de todos los trials, selecciones, predicciones y métricas. Además se ajustaron/puntuaron los modelos externos y controles.

## Evidencia primaria y ejecución

- Dataset original fijado: 82 archivos oficiales Binance, 1.730 días, 2022-01-01–2026-09-26. Artifact 12117929369 del run 39079361222, digest registrado en el protocolo; se volvió a validar el paquete, sin usar un espejo.
- Nueva ejecución: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39081333060
- Job público estándar, 17 segundos (00:03:18–00:03:35Z); ocho tests sintéticos de la búsqueda pasaron antes de procesar datos. Sin GPU, órdenes ni servicios de inferencia.
- Check agregado: https://github.com/joaquinignaciomondaca-code/Idea_3/runs/117538740045 , aplicación github-actions, mismo head SHA. Un estado success significa cálculo/validaciones completados, no modelo financieramente aprobado.
- Python 3.12.3, NumPy 2.2.6, Optuna 4.5.0. Optuna oficial, tag verificado por GitHub API: https://github.com/optuna/optuna/tree/d7e1c1b306b995aa53719ed6ab18e871ae0d52a5 .
- 13.668 eventos en cada ledger externo: 5.460 predicciones aprendidas, 5.460 resultados, 2.730 updates, 12 fits y seis selecciones. Los controles constante/persistencia se puntúan aparte sobre las mismas etiquetas.
- Recuperación autónoma por Checks API: `python -m scripts.fetch_nested_result`. Comprueba fuente, protocolo, revisión, productor, workflow, presupuesto completo y regla de selección; no necesita descargar artifact storage ni inicia otro workflow.

## Resultado

Sobre **1.365 etiquetas externas por predictor**:

| Predictor | Log-loss | Brier |
|---|---:|---:|
| Fijo ajustado | 0.699074 | 0.252853 |
| Fijo sin ajustar | 0.709301 | 0.257304 |
| Adaptativo ajustado | 0.698365 | 0.252538 |
| Adaptativo sin ajustar | 0.713439 | 0.259731 |
| Constante p=0.5 | **0.693147** | **0.250000** |
| Persistencia | 0.698834 | 0.252830 |

Menor es mejor. La búsqueda mejora los agregados frente a los dos controles sin ajustar, pero **no supera la referencia sin señal p=0.5**. Tampoco es una mejora uniforme: en 2024 el fijo sin ajustar obtiene log-loss 0.691623 y el ajustado 0.693470. Se conservan todas las ventanas, todos los candidatos y ambas familias, no solo el período favorable.

No se promueve un ganador, no se amplía automáticamente el espacio al ver que se seleccionaron tasas bajas y no se empieza a operar. No se puede trasladar una mejora de log-loss a rentabilidad de USD 20.

## Límites y siguiente decisión

El histórico BTC ya había sido inspeccionado: los bloques externos están excluidos de esta selección, pero no son un holdout históricamente virgen. La cadena local no es una prueba externa de publicación de pronósticos en esas fechas. No hay certificado point-in-time de disponibilidades/vintages ni prueba de significancia de diferencias temporalmente dependientes.

Antes de pagar complejidad adicional, conviene proponer otro experimento acotado con baselines probabilísticos simples y/o señales adicionales justificadas por fuentes primarias, congelarlo y reservar observaciones futuras. Buscar más trials contra el mismo histórico no convierte esta evidencia en confirmación independiente. La política operativa, sus costos y cualquier objetivo económico constituyen una fase distinta; Laya y evolución poblacional siguen pendientes.

## Archivos y licencia

- Informe completo: `artifacts/nested_optuna/informe.md`.
- Los 30 intentos, pérdidas por fold, tamaños efectivos, selecciones, métricas por bloque y agregadas: `artifacts/nested_optuna/summary.json`.
- Recibo de productor/revisión/hash del agregado: `artifacts/nested_optuna/check_receipt.json`.
- Protocolo: `experiments/nested_optuna_predictive.json` (no modificar tras resultados).
- Software: `microtrade/nested_search.py`, `microtrade/nested_audit.py`, `scripts/run_nested_optuna.py`; workflow `.github/workflows/nested-optuna.yml`.
- Al cierre: 85 tests locales pasaron, incluidos causalidad, repetibilidad, purga de etiquetas, presupuesto y rechazo de recepción alterada.

Fuente de datos: https://data.binance.vision/ . Binance Vision: términos v1.0, CC BY-NC-SA 4.0 salvo designación distinta, investigación no comercial. Informe derivado bajo CC BY-NC-SA 4.0. Términos y atribución acompañan al artifact; registros completos con retención de siete días. Los agregados quedan preservados en Git. No hay aprobación del proveedor ni autorización comercial implícita.
