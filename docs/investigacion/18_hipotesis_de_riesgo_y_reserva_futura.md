# 18 — Hipótesis distinta: persistencia del riesgo y reserva futura

## Investigación y límites antes del cálculo

La pregunta nueva NO es «¿subirá BTC?», sino «¿ayuda la actividad reciente de precios a anticipar el tamaño cuadrático del retorno futuro?». Es útil potencialmente para limitar exposición, pero no implica rentabilidad, señal direccional ni VaR calibrado.

- Patton(2011), artículo de autor: QLIKE y MSE permiten comparaciones robustas bajo condiciones sobre un proxy de volatilidad imperfecto/condicionalmente insesgado. Esas condiciones no se dan por demostradas para BTC. [1](https://public.econ.duke.edu/~ap172/Patton_vol_proxies_JoE_2011.pdf)
- RiskMetrics(1996), ficha del documento técnico en MSCI y edición original: EWMA es un benchmark simple; lambda0.94 es una convención histórica diaria, no un parámetro óptimo demostrado para criptomonedas. [2](https://www.msci.com/www/research-report/1996-riskmetrics-technical/018482266) [1](http://www.phy.pmf.unizg.hr/~bp/TD4ePt_5.pdf)
- Corsi(2009) modela componentes diarios/semanales/mensuales de volatilidad realizada. Nuestros archivos diarios NO contienen realized variance intradiaria: no llamaremos HAR-RV a un modelo de retornos diarios al cuadrado ni diremos que lo replicamos. [1](https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf)
- El estimador de rango log(H/L)^2/(4log2), derivado de Parkinson, utiliza extremos intradiarios; sus supuestos de difusión y ausencia de drift/jumps no están garantizados. Se documenta la fórmula en trabajo de autores de realized range. [8](https://repub.eur.nl/pub/7582/ei2006-10.pdf)

## RISK-PERSISTENCE-001 — diagnóstico retrospectivo preregistrado

Mismos originales oficiales BTCUSDT2022-01-01–2026-09-26, reauditorados, sin espejo. Fuente única piloto no representativa de otros mercados. No es otra búsqueda sobre el clasificador cerrado: target/métodos/métricas distintos, sin presentar sus scores como mejora del log-loss de dirección.

Target y_t=log(close[t]/close[t−1])². Es un proxy ruidoso de segundo momento; interpretarlo como varianza requiere controlar/ignorar justificadamente la media condicional. No es volatilidad latente observada ni realized variance de alta frecuencia.

Forecast emitido con información hasta cierre t−2. Cinco métodos fijados:

1. Constante: media de r² desde02-01-2022 hasta30-12-2022, congelada para toda la evaluación.
2. Rolling20: media de los20 r² conocidos más recientes.
3. Rolling60: media de60 r².
4. EWMA94: inicializar media de los primeros60 r²; recurrencia0.94*v+0.06*r² hasta cutoff. Para dos pasos, mantener la predicción bajo supuesto martingala de varianza/retorno esperado despreciable, no alimentar el día intermedio desconocido.
5. Range20: media20 de log(high/low)²/(4log2). Es información de rango de precios, no más indicadores de dirección.

Piso1e-12 para forecasts de segundo momento; no se ajusta mirando test. No hay optimizer, grid, selección de semillas o hiperparámetros. Se repite dos veces el procedimiento completo. Evaluación2023,2024,2025–26-09-2026:1365 etiquetas por método. Baseline principal de comparación **rolling20**, no solo una constante entrenada en otro régimen.

Métrica primaria QLIKE=log(h)+y/h. Se omiten constantes dependientes solo del resultado; es finita incluso si y=0 y puede ser NEGATIVA. Menor es mejor; no dividir QLIKE para anunciar porcentajes de mejora. Secundaria MSE del proxy, no cambiar después a la métrica favorable. EWMA94/rolling60/range20 vs rolling20: diferencias emparejadas con bootstrap circular por bloque, largos14/60días,2000réplicas,seed1701. Publicar todos los métodos/períodos/intervalos, sin corrección de multiplicidad ni afirmación confirmatoria. No seleccionar ganador por histórico.

## RISK-FORWARD-RESERVED-001 — reserva, todavía NO ejecutada

Ventana fijada ANTES de existir esos resultados: **01-11-2026–31-01-2027**,92 targets diarios UTC. Challenger primario **EWMA94**, referencia **rolling20**, fijados por simplicidad/literatura, NO por el ganador histórico. Se reportarán también los otros tres métodos. No retocar lambda, ventana, piso, horizonte ni métrica al mirar resultados de la reserva.

Para target D:

- Datos completos oficiales hasta cierre D−2; emitir y publicar en D−1 UTC antes de D00:00UTC. Un día completo de latencia, nada de predecir y después obtener timestamp falso.
- Paquete fresco verificado, checksums/recibos y hash del dataset/protocolo. Fallar si fuente atrasada/faltante; no mirrors.
- Registro de creación exclusiva por target; no reescribirlo. Función guard `prospective_record` rechaza datos atrasados/futuros, timestamp sin zona, fecha fuera de reserva o plazo vencido.
- **Un registro local NO prueba emisión prospectiva.** Debe validarse timestamp de publicación externo (p.ej. GitHub Check server completed_at antes de inicio D), app/revisión/protocolo y hashes. Esa integración/publicación automática NO está habilitada aquí.
- Registrar las92 fechas esperadas y todas las faltas/retrasos/fallos. No eliminar las fechas sin forecast ni volver a emitir después de conocer el outcome. Missingness puede estar sesgada.
- Constante histórica debe venir del reporte congelado de RISK-PERSISTENCE-001, no reestimarse usando la reserva.
- Análisis final solo después de madurar el último target y estar disponibles los datos. Mirar resultados parciales para cambiar el procedimiento invalida el carácter confirmatorio.

El protocolo reserva fechas y reglas; hoy no podemos generar o certificar pronósticos de noviembre. **No hay cron/workflow recurrente activado ni pronósticos futuros ya recogidos.** El siguiente gate operativo requiere adquisición fresca, publicación externa puntual y registro de cobertura; no basta con haber escrito este documento.

## Alcance

Solo cálculo público estándar acotado sobre el histórico existente; no servicios premium, GPU, broker, órdenes, PnL deUSD20, Laya ni evolución. Una predicción útil del riesgo no demuestra cómo monetizarla; primero exigir validación futura y luego política operativa/costos/filtros pertinentes, por separado.

Protocolos: `experiments/risk_persistence.json`, `experiments/risk_forward_reserved.json`. Originales Binance Vision https://data.binance.vision/: términos CC BY-NC-SA4.0 salvo designación distinta, solo investigación no comercial. Informe derivado bajo CC BY-NC-SA4.0; términos/atribución en artifact, retención7días, agregados preservados en Git. Sin aval del proveedor.
