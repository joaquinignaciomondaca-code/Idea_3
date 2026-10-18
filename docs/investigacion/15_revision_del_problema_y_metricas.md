# 15 — Revisión crítica: problema, literatura, métricas y siguiente experimento

Fecha: 17-10-2026, Santiago. Investigación metodológica posterior a FEATURE-ABLATION-001. **No se ejecutan nuevas búsquedas ni se sustituyen métricas de experimentos cerrados.**

## Diagnóstico: qué debemos corregir y qué aún no sabemos

Los resultados negativos no prueban un error de programación ni que todo trading predictivo sea imposible. Sí obligan a revisar el diseño antes de sumar modelos. Las pruebas de software y la repetición determinista no son evidencia de ventaja financiera.

La expansión a 24 variables se adelantó a una réplica comparable de un trabajo publicado: coincidían familias de indicadores, pero no necesariamente tarea, horizonte, universo, estimador o evaluación. Esa es una debilidad del planteamiento que debemos corregir, no compensar cambiando de métrica hasta encontrar una favorable.

Hallazgos verificables en el código/protocolo actual:

1. **La etiqueta no es retorno económico futuro general.** Se pronostica si close[i+2]>open[i+2], usando información al cierre i. Se omite la magnitud de la variación y no hay una política de entradas, salidas o abstención. Una predicción acertada de un movimiento diminuto puede no cubrir costos; una equivocación grande puede dominar muchas pequeñas ganancias.
2. **Pocos datos por ajuste, no miles de ejemplos de entrenamiento.** Hay 1.730 días totales y 1.365 etiquetas externas, pero cada fit usa como máximo365 ejemplos maduros. En la primera validación interna, julio2022, el warmup90 y la purga dejan solo88 ejemplos para el modelo completo de25 coeficientes, incluido el intercepto. Esto indica fragilidad potencial; no demuestra por sí solo sobreajuste como causa del resultado.
3. **24 columnas no son24 fuentes independientes.** En señales brutas existe la identidad exacta return_1 = intraday_return + open_gap. Otros horizontes comparten observaciones. El escalado/clipping cambia la representación, no añade nueva información. Las ablaciones son condicionales a las otras columnas y al estimador; sus efectos no se suman.
4. **Fijo/adaptativo no son dos familias de ML distintas.** Ambos son logística SGD con la misma receta inicial. No se verificó todavía el ajuste frente a un solver independiente del mismo objetivo ni se documentaron curvas de convergencia. Diez épocas son una elección, no un certificado de convergencia.
5. **Faltan baselines más completos.** Además de p=0.5 y persistencia, se debe incluir una probabilidad histórica suavizada, estimada exclusivamente con etiquetas maduras del entrenamiento. Para retornos: cero y media histórica; para una política: efectivo y buy-and-hold con reglas/costos comparables.
6. **No se ha cuantificado incertidumbre de las diferencias.** El promedio agregado no establece significancia. Folds y versiones fija/adaptativa comparten datos y no son réplicas independientes. Un bootstrap temporal o test apropiado requiere las pérdidas individuales originales y supuestos explícitos, no tratar1.365 días como1.365 ensayos independientes.
7. **Reutilización del histórico.** Nuevos experimentos sobre BTC ya inspeccionado siguen siendo exploración retrospectiva. Selección anidada evita una fuga algorítmica concreta, pero no borra decisiones humanas influidas por resultados anteriores.

No se declara un bug confirmado: falta una auditoría independiente numérica. No se modifican las series de resultados ni los protocolos anteriores.

## Qué dicen otros trabajos y qué NO podemos trasladar directamente

### A. Gu, Kelly y Xiu — Empirical Asset Pricing via Machine Learning (2020)

La versión publicada estudia aproximadamente30.000 acciones,1957–2016, con94 características, variables macro e interacciones que superan900 señales. Analiza retornos y su ordenamiento entre acciones; no es una prueba de clasificación intradía de BTC. Reporta información importante en tendencias, liquidez y volatilidad. El número de observaciones y la estructura de panel son muy distintos de un solo activo y365 filas de train. [3](https://academic.oup.com/rfs/article/33/5/2223/5758276)

**Lección propuesta:** reproducir tarea/estimador/benchmark y no solo copiar nombres de indicadores. No importar Sharpe ni rentabilidad publicados como expectativa para USD20.

### B. Machine learning and the cross-section of cryptocurrency returns (2024)

La publicación editorial describe más de500 criptomonedas/tokens,2017–2023,40 características y ocho modelos. Reporta limitaciones materiales: concentración de alpha en monedas pequeñas/ilíquidas/volátiles, trading intenso y riesgos de caída. Es predicción transversal y construcción de carteras, no nuestro objetivo binario de un solo BTC. [1](https://www.sciencedirect.com/science/article/abs/pii/S1057521924001765)

**Control de versiones:** un borrador2023 de conferencia presenta34 señales y conclusiones sobre predominio de posiciones cortas diferentes de los highlights de la publicación2024, que destacan las largas. No se mezclan esas versiones para describir un único resultado. Para replicar se debe fijar la versión y revisar métodos, universo, cartera y tablas completos; el resumen editorial por sí solo no basta. [1](https://www.sciencedirect.com/science/article/abs/pii/S1057521924001765) [3](https://affi2023.eventsadmin.com/Papers/ViewContribution?cid=8390&h=A0CBBA4C296557EB2205D3ECCD9DBD7F)

**Lección propuesta:** cualquier aparente ventaja en microcoins debe pasar controles de supervivencia, exclusión de monedas desaparecidas, liquidez, disponibilidad histórica y ejecución. No proponer shorts ni diversificación de cientos de posiciones conUSD20.

### C. A Trend Factor for the Cross Section of Cryptocurrency Returns — CTREND

La publicación2025 describe más de3.000 monedas,2015–2022 y28 señales técnicas; combina pronósticos con un estimador combinado elastic net transversal. Las carteras del estudio se rebalancean semanalmente. El artículo incluye evaluaciones con costos y restricciones de universo. Eso no equivale a clasificar el color de una vela con dos días de antelación, ni confirma que sus costos sean los nuestros. [2](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/4C1509ACBA33D5DCAF0AC24379148178/S0022109024000747a.pdf/trend_factor_for_the_cross_section_of_cryptocurrency_returns.pdf)

**Lección propuesta:** combinación regularizada de señales y objetivo/horizonte alineados. No es necesario ejecutar todavía el artículo completo ni prometer replicarlo con tres activos, porque eso sería otro universo y otro experimento.

### D. Gneiting y Raftery — Strictly Proper Scoring Rules, Prediction, and Estimation (2007)

El trabajo fundamenta las reglas de puntuación propias; incluye el score logarítmico y el cuadrático/Brier. Son adecuados para evaluar honestamente probabilidades de eventos. Un resultado negativo con esas métricas no las convierte en métricas equivocadas. Pero puntuar probabilidades no sustituye una función de decisión financiera. [1](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf)

### E. Bailey, Borwein, López de Prado y Zhu — sobreajuste de backtests

El trabajo muestra los riesgos de seleccionar estrategias probando múltiples configuraciones y propone evaluar probabilidad de sobreajuste con CSCV/PBO. No se ha calculado PBO en nuestro laboratorio y no se interpretará un simple holdout como protección total frente a investigación repetida. Tampoco se sustituirá automáticamente una evaluación cronológica por particiones que ignoren la disponibilidad temporal. [2](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

Para una comparación formal de múltiples pronósticos, SPA/Reality Check es otra referencia: contempla dependencia de pérdidas y multiplicidad. No se ha ejecutado este test ni se considera una cura para sesgos de datos o investigación no registrados. [2](https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparison-reference.html)

## Métricas: completar el tablero sin escoger retrospectivamente la ganadora

Las siguientes son propuestas de evaluación, no resultados calculados.

| Pregunta | Métrica principal propuesta | Complementos y controles |
|---|---|---|
| ¿La probabilidad de subir mejora a un predictor simple? | Mantener log-loss y Brier | Skill relativo a p=0.5 y a prior histórico entrenado; calibración; ROC-AUC como ranking, no sustituto de calibración; acierto y frecuencia de clase como secundarios |
| ¿Predice la magnitud del retorno? | Error cuadrático y R² fuera de muestra respecto de cero/media histórica pasada | MAE, errores por régimen; evitar R² sobre niveles de precio como demostración de rentabilidad |
| ¿Ordena activos de forma útil? | Spearman/Rank IC transversal, por fecha | Estabilidad temporal, cartera por cuantiles neta de costos cuando sea ejecutable. No presentarlo como experimento transversal robusto con solo tres monedas |
| ¿Predice riesgo/volatilidad? | QLIKE para varianza positiva y/o error de varianza | Comparar con volatilidad histórica/EWMA; target propio, no declarar resuelta la predicción de dirección por mejorar riesgo |
| ¿Una política concreta sirve con microcapital? | Resultado neto frente a efectivo y buy-and-hold, bajo costos/filtros comprobados | Sharpe con supuestos temporales, drawdown, turnover, número de operaciones, exposición y cobertura/abstención. No evaluar un máximo Sharpe elegido entre muchos umbrales sobre test |

En la política operativa los tamaños de movimientos importan. Como ejemplo conceptual sin costos: acertar60 veces ganando1 y fallar40 perdiendo2 suma−20 aunque el acierto sea60%. Es aritmética ilustrativa, no un backtest de nuestro modelo.

Usar varios indicadores no autoriza elegir después el que dé verde. Antes del siguiente experimento se fija una métrica primaria acorde a SU tarea, y se publican los secundarios completos. Una métrica con pocos trades, varianza casi nula o un período favorable requiere cautela, no un score espectacular como prueba.

## Orden de trabajo recomendado antes de más búsquedas

1. **Auditoría numérica independiente.** Verificar gradientes y convergencia del ajuste actual contra un solver de referencia con el mismo escalado, penalización/intercepto, datos y normalización del objetivo. No asumir equivalencia entre parámetros C de una librería y nuestro L2 sin derivarla. Revisar columnas redundantes y disponibilidad. Estas pruebas no cuentan como evidencia de mercado.
2. **Tabla de réplica antes del nuevo modelo.** Elegir un trabajo con tarea reproducible mediante fuentes primarias accesibles; documentar versión, universo, fecha de señal, etiqueta, horizonte, splits, modelo, costos y datos ausentes. Si solo podemos adaptar momentum o elastic net, llamarlo adaptación parcial, no réplica exacta.
3. **Elegir UNA tarea económica concreta.** Para spot con microcapital puede ser retorno futuro/riesgo y decisión long/efectivo en activos líquidos, sin shorts ni fragmentación en decenas de órdenes. No fijar aún ventana7/14días como ganadora porque no se ha probado; justificar un horizonte en literatura/ejecución y congelarlo antes del cálculo.
4. **Preregistro nuevo y presupuesto pequeño.** Baselines fuertes; comparar un modelo lineal regularizado y como máximo una alternativa no lineal pequeña, en vez de cientos de modelos. No reusar los scores externos del laboratorio para elegir umbrales o métricas.
5. **Evaluación honesta.** Ventanas temporales con purga acorde al horizonte, pérdida diferencial por observación y estimación de incertidumbre temporal/multiplicidad cuando proceda. Un análisis retrospectivo adicional sigue etiquetado como exploración.
6. **Confirmación futura y fase económica separada.** Mantener datos futuros realmente no inspeccionados; incorporar costos aplicables y filtros/tamaños mínimos antes de afirmar utilidad paraUSD20. No pedir al usuario descargas manuales ni iniciar servicios pagados.

## Qué se hizo en esta revisión

Se contrastaron fuentes primarias/editoriales/de autores y documentación de métodos con los archivos locales `experiments/feature_ablation.json`, `microtrade/feature_study.py` y los agregados registrados. No se adquirieron nuevos datos de mercado, no se instalaron paquetes, no se ejecutaron otros fits, no se recalcularon resultados ni se cambió una métrica del protocolo cerrado. La auditoría numérica independiente y el siguiente experimento siguen pendientes.
