# 16 — Auditoría numérica independiente y adaptación semanal acotada

## Diseño fijado antes del cálculo

Se ejecutarán dos tareas SEPARADAS, sin alterar los protocolos cerrados ni buscar nuevas métricas sobre sus predicciones. Fuente: originales Binance Vision adquiridos en run39079361222, artifact12117929369. Solo investigación no comercial; no órdenes, cómputo premium ni inferencia pagada.

### 1. NUMERICAL-AUDIT-001: resolver la duda numérica

Objetivo exacto de entrenamiento anterior:

```text
J(w) = mean(log(1+exp(Xw)) - y*Xw) + (L2/2)*sum(w_no_intercept**2)
```

Se respeta media en lugar de suma, L2=0.01 e intercepto sin penalizar. El valor C de otra librería no se equipara sin derivar su normalización.

Siete casos: los seis fits iniciales originales all24/baseline3 de2023/2024/2025, más el primer fit interno all24 de88 ejemplos. Los pesos, escalas y fechas originales se obtienen del artifact fijado12119213800 del run39082812342; su resultado completo debe coincidir con el hash ya registrado en Git. Fijo/adaptativo tenían el mismo fit inicial.

Controles:

- Gradiente analítico contra diferencias finitas centrales y promedio de los pasos SGD de producción.
- Hessiano definido positivo en los casos auditados.
- Newton/Armijo independiente y SciPy1.15.3 L-BFGS-B con otra expresión del objetivo y gradiente numérico de tres puntos. Máximos100/2000 iteraciones, tolerancias previas en experiments/numerical_audit.json.
- Reconstrucción del SGD original en época10 frente a los pesos anteriores; trayectorias de train en épocas0/1/10/100/1000 para observar convergencia, no escoger época por score externo.
- Abortamos si hay desacuerdo, datos/registro diferentes o logits con clipping activo>=35. Si diez épocas NO convergen, se publica ese diagnóstico; no se considera un fallo de la auditoría ni evidencia de que corregirlo vaya a mejorar fuera de muestra.

No se predicen ni puntúan nuevamente ventanas externas del experimento anterior. Converger en train no garantiza generalización ni explica causalmente los scores históricos.

### 2. WEEKLY-RETURN-ADAPTATION-001: pregunta nueva, método cerrado

Referencia: Liu y Tsyvinski, **Risks and Returns of Cryptocurrency**, working paper NBER24877 (2018), componente de momentum temporal semanal. El trabajo estudia momentum y atención a frecuencias diarias/semanales y reporta horizontes semanales. [1](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf?fid=%5BContact.fid%5D%3Ffid)

**Es adaptación parcial, no réplica exacta.** No se reproducen período original, proveedores, otros activos, factores de atención/red, clasificación por quintiles o rentabilidades publicadas. Tampoco es réplica de CTREND, que es transversal. Se conserva una pregunta replicable con nuestros originales: ¿momentum temporal ayuda a pronosticar magnitud de retorno semanal fuera de muestra?

| Componente | Regla congelada |
|---|---|
| Universo/fuente | Solo BTCUSDT spot del paquete oficial2022-01-01–2026-09-26; no representativo de otros mercados |
| Señal | Domingo después del cierre UTC, con84 retornos diarios de warmup |
| Objetivo | close[t+8]/open[t+2]−1: siete sesiones de martes a lunes, tras dejar un día completo entre señal y apertura de referencia |
| Disponibilidad | Target de train debe haber terminado a más tardar en el primer cutoff del bloque. No rellenar targets incompletos al final de2026 |
| Variables | Momentum logarítmico7/28/84 días y volatilidad poblacional28 días; no equivalen a cuatro fuentes independientes |
| Modelos | OLS con intercepto y momentum7; ridge con cuatro variables, alpha1 fijo. Solución cerrada/lstsq, sin SGD ni búsqueda de convergencia |
| Ridge | MSE medio + alpha*sum(coeficientes_no_intercepto²); ecuaciones XTX/n + alpha*diag(0,1,1,1,1) |
| Escala | Mediana/IQR de train, IQR0->1, clipping[-5,5]; congelada. OLS usa la misma columna de momentum7 |
| Baselines | Retorno0 y media histórica calculada solo en el train maduro de cada bloque |
| Bloques | Señales de2024,2025,2026 con labels completos; reinicio al primer domingo de cada año, train expansivo, mínimo60 semanas, pesos congelados ese año |
| Métrica primaria | MSE y su skill R²_OOS=1−MSE_model/MSE_media_histórica. Agregado por observaciones, no promedio simple de bloques |
| Secundarias | MAE y dirección a umbral0 fijado antes de ver resultados; no seleccionar modelo por alguna que salga favorable |
| Incertidumbre | Diferencia emparejada de pérdidas cuadráticas frente a media histórica: bootstrap circular dentro de cada año, bloques4 y12 semanas,2000réplicas, semilla1701, intervalos percentiles95%. Ambos largos publicados |
| Presupuesto | Seis fits OLS/ridge por pasada, dos pasadas idénticas=12 fits. Tres medias por pasada y predictor0. Cero HPO, selección de horizonte o umbral |

La apertura es una **referencia de precio**, no un fill garantizado. La etiqueta es retorno BTCUSDT, no retorno exacto en USD ni exceso sobre tasa libre de riesgo. No se simula una política de posiciones ni se calculan PnL, Sharpe, costos o rentabilidad deUSD20. Un resultado favorable en otra tarea NO rescata el log-loss de la tarea anterior.

Los intervalos son exploratorios: no corrigen multiplicidad/investigación previa y no convierten el histórico ya inspeccionado en holdout virgen. Que los intervalos de tenencia no se solapen no hace independientes las observaciones. No se elige el largo de bloque que dé una conclusión favorable ni se promueve un ganador por externos. Si los datos son pocos, se reporta la limitación.

## Integridad y entregables previstos

- Protocolos `experiments/numerical_audit.json` y `experiments/weekly_return_adaptation.json`, fijados antes de procesar datos.
- Dos Checks separados: auditoría numérica train-only y adaptación semanal con métricas nuevas. Success significa cálculo/controles completados, no ventaja financiera.
- El workflow público estándar `numerical-audit.yml` tiene límite10minutos, dependencias fijadas y no ejecuta los workflows previos. Si falla la auditoría numérica, no pasa al estudio semanal.
- Registros completos y términos/atribución en artifact con retención7días; agregados/recibos preservados en Git. La auditoría no es una certificación externa de pronósticos históricos.
- No adquirir otros datos ni recurrir a espejos si expiran los artifacts fijados. Recuperación autónoma de agregados por Checks API, sin descargas manuales para el usuario.

Fuente y productos derivados: Binance Vision, https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta. Investigación no comercial, sin patrocinio/aprobación del proveedor. Informes derivados bajo CC BY-NC-SA4.0.
