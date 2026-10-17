# Replay predictivo con velas oficiales — ejecutado y recuperado

17-10-2026. **Avance completado sin intervención manual del usuario y sin trading real.**

## Qué cambió respecto de la etapa anterior

Los archivos ya estaban adquiridos en el runner, pero el host del artifact impedía recuperarlos aquí. Se llevó el cálculo al mismo entorno donde están disponibles y se publicó únicamente el resultado agregado mediante GitHub Checks. La API de GitHub sí es accesible desde el laboratorio.

No se usó un proxy ni se hicieron públicos secretos. No se transfirieron series completas a Git: los originales y ledgers siguen en artifacts con retención de siete días. La falta de precios locales ya no impide leer y validar el informe del cálculo remoto.

## Protocolo congelado y ejecución

- [BINANCE-PRIMARY-PREDICTIVE-001](../../experiments/binance_primary_predictive.json), publicado **antes** de calcular las métricas de estas velas.
- Fuente fijada: adquisición [run 39079361222](https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39079361222), artifact `12117929369`, digest registrado en protocolo. Se comprobó que no estuviera expirado y correspondiera a su revisión de origen.
- Replay: [run 39080171438](https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39080171438), commit `0be6d81569462d3956d1d5f476a1fa0dd3fb4dfd`, **success**. Job completo: aproximadamente 11 segundos, según los tiempos de GitHub.
- Antes del cálculo se reauditaron ZIP, checksums, recibos y cobertura: **82/82 archivos, 1.730/1.730 fechas**, sin errores, huecos ni fechas extra.
- Precio usado: open/close reales BTCUSDT spot, no aperturas reconstruidas desde cierres.
- Entrenamiento inicial hasta 31-12-2022; pronósticos registrados desde corte 01-01-2023 sobre la dirección intradía de i+2. Primer objetivo 03-01-2023, último 26-09-2026.
- Predictor fijo vs adaptativo con idénticos pesos iniciales; regresión logística stdlib, features e hiperparámetros del protocolo inicial. Sin Laya, búsqueda de parámetros, población ni selección por resultados.
- Control p=0,5 y persistencia de la última dirección intradía con probabilidades 0,55/0,45.
- Dos corridas completas, igualdad exacta de todas las métricas y snapshot inicial. **2.726 predicciones evaluadas, 1.363 actualizaciones adaptativas** posteriores al feedback.

El revisor permitió este diagnóstico predictivo acotado por la cadena CI/artifact fijada y la reauditoría original. **No habilitó el gate económico general** del laboratorio. La salida del auditor genérico sigue exigiendo revisión de costos/filtros y no debe modificarse para simular una aprobación comercial o de trading.

## Resultado

[Informe completo](../../artifacts/binance_primary_predictive/informe.md), [summary](../../artifacts/binance_primary_predictive/summary.json), [recibo del Check](../../artifacts/binance_primary_predictive/check_receipt.json).

En 2025–26-09-2026, 634 etiquetas:

| Predictor | Brier ↓ | Log-loss ↓ | Acierto |
|---|---:|---:|---:|
| Fijo | 0,265764 | 0,727340 | 49,53% |
| Adaptativo | 0,259770 | 0,713289 | 47,48% |
| Constante p=0,5 | 0,250000 | 0,693147 | 50,32%* |
| Persistencia | 0,255497 | 0,704186 | 47,00% |

\* Para p=0,5 el desempate predice siempre «no sube»; no es una moneda simulada. En Brier y log-loss representa incertidumbre 50/50.

En **ambas épocas**, fijo y adaptativo tienen peores Brier/log-loss que el control constante. El adaptativo mejora esos scores frente al fijo, pero no demuestra señal útil frente a la referencia sin información. No se promueve ningún modelo ni se retocan parámetros para arreglar el resultado.

## Recuperación comprobable

El propio job publica un Check `Primary predictive replay — aggregate report` mediante un token efímero con permisos mínimos. La recuperación verifica app `github-actions`, revisión, run exitoso, experimento, fuente y hash del protocolo, y rechaza campos de observaciones/cuentas o una aprobación de trading.

```bash
python -m scripts.fetch_primary_predictive_result
```

No inicia ni repite un runner: obtiene el informe existente a través de la API. El Check leído tiene ID `117535369229`. El resultado y su recibo se conservaron aquí y se pueden versionar sin precios originales. No se afirma que la cadena hash sea un timestamp externo ni una firma del exchange.

## Pruebas y alcance pendiente

**73 tests pasaron localmente**: los 63 anteriores, siete del adaptador primario y tres de recuperación del Check. Los siete tests del adaptador también pasaron en el runner antes de procesar datos reales. Fixtures sintéticos prueban software; la reauditoría remota prueba coherencia/procedencia del paquete adquirido.

Sigue pendiente:

- Verificación de costos, filtros del par y presupuesto desde USD 20. No se calculó PnL ni se afirmó rentabilidad neta.
- Comparación contra el espejo histórico anterior; el replay no lo consume.
- Disponibilidad histórica real, vintages y tiempos de publicación de las velas; no es estudio point-in-time certificado.
- Un forward genuino iniciado tras congelamiento. Las épocas BTC ya eran conocidas; no hay holdout independiente ni prueba estadística de superioridad.
- Licencias para producción/comercio. Fuente y resultados derivados bajo los términos de Binance Vision/CC BY-NC-SA 4.0 para investigación no comercial, salvo designación distinta. Atribución Binance Vision, sin patrocinio ni aprobación del proveedor.
- Laya y evolución de cinco modelos: no ejecutados. Más candidatos sin un diseño de selección temporal separado aumentarían el riesgo de encontrar un ganador por azar.

La etiqueta Coin Metrics del experimento previo era close→close de una referencia, mientras que aquí es open→close intradía del mercado. No comparar diferencias de scores como una competencia controlada entre proveedores.
