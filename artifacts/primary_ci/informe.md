# Adquisición oficial Binance en GitHub Actions

**Estado: adquisición y auditoría remotas terminadas correctamente. Sin trading real.**

Fecha: 17-10-2026. Se verificó mediante la API de GitHub que `joaquinignaciomondaca-code/Idea_3` ya es público. Se publicó únicamente el workflow y los tres scripts stdlib necesarios, junto con `.gitignore`, en la rama `arena/214e9ea3-idea-3`. No se cambió `main`, no se abrió/mezcló PR ni se publicaron las series locales del laboratorio.

## Ejecución comprobada

- [Run 39079361222](https://github.com/joaquinignaciomondaca-code/Idea_3/actions/runs/39079361222): **success**.
- Commit ejecutado: `08eb12e0e22f32362383fb78bcbd34ab74b0eee7`.
- Job `collect-and-audit`: completó en 51 segundos según el monitor de GitHub.
- Runner estándar `ubuntu-latest`, timeout de 10 minutos, sin broker ni credenciales de trading. No se aprovisionaron runners de pago, nube o suscripciones externas.
- Una ejecución previa quedó **skipped**, sin ejecutar el job: la firma de coautor añadida al commit impedía la comparación exacta del mensaje. Se corrigió el guard usando su prefijo. No fue un fallo de adquisición de datos.

El plan congelado exige **82 ZIP oficiales, checksums y recibos**, BTCUSDT spot diario, **01-01-2022 a 26-09-2026**, **1.730 fechas esperadas**. El auditor estricto solo termina con éxito si el paquete tiene todos los archivos, recibos, hashes y cobertura requeridos; este paso terminó con éxito en GitHub. Es evidencia de la ejecución del auditor, no una lectura local del JSON interior del artifact.

## Originales conservados

Artifact: `primary-BTCUSDT-39079361222-1`.

- ID: `12117929369`.
- Tamaño reportado por GitHub: 364.613 bytes.
- Digest reportado por GitHub: `sha256:af7208f3daaacc306b2e2d752bab6f4d1a47642555e423abdb82f87ec6f40278`.
- Conserva archivos originales, `.CHECKSUM`, recibos de adquisición directa, plan, CSV candidato, informe de auditoría, atribución y términos oficiales.
- Retención configurada: 7 días; el resumen JSON registra la expiración devuelta por GitHub. No es almacenamiento permanente.

## Límite de recuperación local

Se intentó recuperar el artifact con `gh run download`. La descarga de GitHub se redirige a su almacenamiento de resultados, fuera de los hosts permitidos en este sandbox, y falló. **No se repitió el intento ni se usó un proxy.** Por tanto:

- Originales adquiridos y auditados en el runner: **sí**.
- ZIP/velas recuperados en el laboratorio local: **no**.
- JSON interno del informe leído localmente: **no**.
- Comparación local contra el espejo anterior con esos originales: **pendiente**. El runner no tenía ese espejo; su auditoría no verifica coincidencia con él.
- Entrenamiento local o remoto con estas velas: **no ejecutado**.
- Tarifas, filtros vigentes, fondeo y ejecución aprobados: **no**.

La siguiente evaluación puede ejecutarse junto a los datos en el runner; no es necesario pedir al usuario que descargue archivos por E2B. Requiere preparar y auditar ese experimento y conservar sus resultados de manera accesible. Esto no se presenta como ya realizado.

## Licencia y uso

El workflow conserva los términos oficiales de Binance Vision de la revisión `d571690eb66760763b0bd6e27e8cd35603c7e244` y atribución al origen `https://data.binance.vision/`. Los términos leídos establecen **CC BY-NC-SA 4.0**, salvo designación distinta, con restricciones de uso no comercial/producción. No tratar el MIT del código de descarga como licencia comercial de los datos. La descarga y auditoría son investigación no comercial; no autorizan trading real ni un producto comercial.

## Verificación local adicional

Se ejecutó la suite completa: **63 tests pasaron**. Son verificaciones de software, no validación independiente de precios o rentabilidad. El resumen legible por máquina es `summary.json`, con metadatos reales de run/artifact y las limitaciones anteriores.

## Actualización posterior: cálculo y lectura remotos resueltos

Se ejecutó el predictor sobre el artifact original en el runner y se recuperó
el informe agregado mediante GitHub Checks API. Ver [replay ejecutado](../binance_primary_predictive/informe.md).
Las limitaciones de recuperación de ZIP arriba describen la etapa anterior:
los ZIP siguen sin importarse aquí, pero **los resultados ya se calcularon y se
leyeron localmente**. No se habilitó trading ni se verificaron costos/filtros.
