# Hipótesis de riesgo: persistencia y reserva futura

Ejecución histórica: https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39085620035

**Nueva pregunta: tamaño cuadrático del retorno, NO dirección ni rentabilidad. Solo diagnóstico retrospectivo; reserva futura aún sin activar.**

## Reglas fijadas antes del cálculo

- Originales oficiales BTCUSDT,82 archivos/1730días. Forecast con datos hasta t−2; target log(close[t]/close[t−1])². Proxy ruidoso de segundo momento, no varianza latente observada. Interpretación como varianza requiere media condicional despreciable.
- Cinco métodos sin HPO: constante media2022 hasta30diciembre; medias móviles20/60 de r²; EWMA lambda0.94 inicializado con60retornos; rango20 mean(log(H/L)²/(4log2)). Rango presupone dinámica de difusión, sin garantía de ausencia de drift/jumps.
- QLIKE primaria=log(h)+y/h. Se omiten constantes comunes al outcome. **Puede ser negativa: menor es mejor.** No convertir cocientes QLIKE en porcentajes de mejora. MSE del proxy secundaria.
- Dos pasadas idénticas. Todos los métodos/períodos publicados, sin elegir ganador. No es HAR-RV: faltan datos intradiarios de realized variance.

## Agregado:1.365 targets de2023 a26-09-2026

| Método | QLIKE ↓ | MSE ↓ | Media forecast | Media proxy |
|---|---:|---:|---:|---:|
| constant_train | -6.259180 | 2.187753050e-06 | 0.0011448 | 0.0005877 |
| rolling20 | -6.206469 | 1.977192690e-06 | 0.0005839 | 0.0005877 |
| rolling60 | -6.369234 | 1.924539084e-06 | 0.0005854 | 0.0005877 |
| ewma94 | -6.386051 | 1.916239963e-06 | 0.0005846 | 0.0005877 |
| range20 | -6.353514 | 1.936920471e-06 | 0.0006398 | 0.0005877 |

EWMA94−rolling20: ΔQLIKE=-0.179583. Reducción de MSE=3.08% frente a rolling20. Este porcentaje es reducción de error, **no rentabilidad**.

## Incertidumbre exploratoria, todas las comparaciones

Diferencias QLIKE método−rolling20; negativo favorece método. Bootstrap circular dentro de cada bloque,2000réplicas,seed1701,14/60días. Sin corrección por multiplicidad ni investigación previa, no prueba confirmatoria.

| Método | Bloque días | Delta | Inferior95% | Superior95% |
|---|---:|---:|---:|---:|
| ewma94 | 14 | -0.179583 | -0.328155 | -0.064745 |
| ewma94 | 60 | -0.179583 | -0.295322 | -0.083209 |
| range20 | 14 | -0.147045 | -0.271434 | -0.046865 |
| range20 | 60 | -0.147045 | -0.237150 | -0.070636 |
| rolling60 | 14 | -0.162765 | -0.351088 | -0.004283 |
| rolling60 | 60 | -0.162765 | -0.293848 | -0.044126 |

## Todos los bloques

| Período | Método | n | QLIKE ↓ | MSE ↓ |
|---|---|---:|---:|---:|
| 2023-01-01 a 2023-12-31 | constant_train | 365 | -6.313713 | 1.843028853e-06 |
| 2023-01-01 a 2023-12-31 | ewma94 | 365 | -6.393597 | 1.499569518e-06 |
| 2023-01-01 a 2023-12-31 | range20 | 365 | -6.300363 | 1.544223228e-06 |
| 2023-01-01 a 2023-12-31 | rolling20 | 365 | -5.890896 | 1.579216081e-06 |
| 2023-01-01 a 2023-12-31 | rolling60 | 365 | -6.443512 | 1.505624089e-06 |
| 2024-01-01 a 2024-12-31 | constant_train | 366 | -6.106109 | 2.360820682e-06 |
| 2024-01-01 a 2024-12-31 | ewma94 | 366 | -6.131961 | 2.266570780e-06 |
| 2024-01-01 a 2024-12-31 | range20 | 366 | -6.155799 | 2.245446731e-06 |
| 2024-01-01 a 2024-12-31 | rolling20 | 366 | -6.106307 | 2.277104378e-06 |
| 2024-01-01 a 2024-12-31 | rolling60 | 366 | -6.104918 | 2.288928218e-06 |
| 2025-01-01 a 2026-09-26 | constant_train | 634 | -6.316151 | 2.286304435e-06 |
| 2025-01-01 a 2026-09-26 | ewma94 | 634 | -6.528390 | 1.953879763e-06 |
| 2025-01-01 a 2026-09-26 | range20 | 634 | -6.498252 | 1.984891894e-06 |
| 2025-01-01 a 2026-09-26 | rolling20 | 634 | -6.445969 | 2.033176576e-06 |
| 2025-01-01 a 2026-09-26 | rolling60 | 634 | -6.479058 | 1.955355409e-06 |

## Qué significa y qué no

- El diagnóstico permite estudiar predictibilidad del riesgo por separado de dirección. No rescata el clasificador anterior ni implica una estrategia rentable.
- EWMA no es uniformemente el mejor método en cada período. También hay otros métodos que pueden mejorar al benchmark; no se proclama ganador universal.
- QLIKE/MSE tienen fundamentos para proxies bajo supuestos: no certificamos insesgadez condicional del proxy BTC. Dos días de horizonte, ruido, no estacionariedad y tamaño muestral limitan las conclusiones.
- No se calcula VaR/ES calibrado, Sharpe, posiciones o PnL USD20. Menor error de riesgo puede servir para investigar límites de exposición, pero falta política y costos verificables.

## Reserva futura, no resultados futuros

**01-11-2026 a31-01-2027:92targets diarios UTC.** EWMA94 challenger primario y rolling20 referencia, elegidos en el protocolo ANTES del histórico; no cambiar por el ganador observado. Mantener los cinco métodos en el reporte.
- Para target D: input oficial completo hasta cierre D−2, emisión/publicación en D−1 UTC antes de D00:00. No backfill; registrar cada falta/retraso entre las92 fechas.
- El guard local de creación exclusiva está implementado/probado con fixtures; un archivo local no acredita publicación prospectiva.
- Check.completed_at por sí solo no basta: la API permite suministrarlo/editar output. Antes de activar se requiere artifact ID/digest vinculado a bytes, created_at del servicio antes del target y workflow/head/protocolo correctos, con verificación de bytes.
- **No hay cron, colección ni publicación futura habilitada.** Falta integrar adquisición fresca/publicación y conservación verificable de evidencia durante toda la reserva; la retención7días histórica es insuficiente. No se autoriza almacenamiento recurrente pagado.
- No actualizar métodos por resultados parciales. Análisis al final de la ventana; incluso entonces se deben declarar cobertura, missingness y supuestos.

## Trazabilidad

Protocolo histórico y código publicados antes del cálculo; dos pasadas idénticas en cada forecast/outcome/métrica/intervalo. Historial ya inspeccionado, no holdout virgen. Success significa ejecución/controles completados, no aprobación financiera.

Registros completos en artifact con retención7días; agregados/recibo en Git. Protocolos: experiments/risk_persistence.json y experiments/risk_forward_reserved.json; fuentes y matriz de hipótesis en docs/investigacion/18_hipotesis_de_riesgo_y_reserva_futura.md.

```bash
python -m scripts.fetch_risk_result
```

Solo recupera resultados existentes por Checks API; no inicia cálculos ni reserva activa. Datos: Binance Vision https://data.binance.vision/, términos CC BY-NC-SA4.0 salvo designación distinta, investigación no comercial; informe derivado bajo CC BY-NC-SA4.0. Atribución/términos en artifact; sin aval del proveedor.
