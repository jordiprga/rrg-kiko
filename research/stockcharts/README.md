# Contraste semanal con StockCharts

**Actualización, ronda 2:** SMA 10/30/9 supera los criterios y la confirmación nueva con 52 semanas de NYSE Composite. El resultado EMA que sigue es el registro de la primera ronda, ya superado. Véase [protocolo de la ronda 2](protocol-v2.json) y ejecutar `python -m scripts.refine`.

Investigación del 18/10/2026. No forma parte del directorio público de la web.

`observations.csv` conserva 52 fechas efectivas por activo, desde 24/10/2025 hasta 16/10/2026: `$COMPQ`/`^IXIC` y `$INDU`/`^DJI`, benchmark `$SPX`/`^GSPC`. Cada fila incluye cierres, fuente y precisión. `source.json` describe la inversión de las coordenadas SVG, sus límites y un ejemplo de calibración. `read-visible-svg.js` conserva el procedimiento de lectura de los elementos dibujados. No se consultan variables internas de la web.

Los valores son reconstrucciones del SVG, con incertidumbre conservadora ±0,01 por eje. No son valores de un tooltip numérico ni estimaciones de píxeles de las capturas. En los primeros seis puntos del Dow se usaron los círculos de cola de la ventana de 30 terminada el 22/05/2026: las cabezas se fijaban al borde de la escala visible y daban coordenadas falsas. El benchmark y los precios proceden de los textos de la web.

Se comprobó una cola de 30 y una de 10: N círculos pequeños más la cabeza actual. Las fechas festivas se guardan con la última sesión real, no con un viernes inventado.

`protocol.json` fija el reparto cronológico y los criterios antes de la primera búsqueda. Nasdaq: 36 fechas de ajuste, 16 reservadas. Todo Dow reservado. Se probaron 5.160 combinaciones EMA con escalas positivas centradas en 100, estimadas exclusivamente en el ajuste. No se amplió la búsqueda después de ver la evaluación.

La mejor candidata usa suavizado 10, referencia 24, momentum 13 y escalas X=0,9271679043 / Y=1,0855665210. Alcanza los cuadrantes y el sentido del último tramo de ambos casos de Kiko, pero **no supera la validación independiente**:

| Evaluación | RMSE X/Y actual | RMSE X/Y candidata | Cuadrantes candidata |
|---|---|---|---|
| Nasdaq reservado | 2,071 / 1,201 | 0,814 / 0,475 | 66,7 % |
| Dow completo | 1,724 / 1,108 | 0,656 / 0,392 | 72,5 % |

Se conserva `relative-ema-v1`. El umbral es 0,20 por eje y 95 % de cuadrantes. Suavizado y momentum óptimos están en el límite de la búsqueda; ampliar el espacio sería otro experimento, con nueva evaluación independiente para no reutilizar estos resultados como ajuste.

Los cierres casi coinciden: error absoluto máximo S&P 500=0,0002344; Dow=0,001875; Nasdaq=0,0109375. No explican por sí solos discrepancias de varios puntos en los indicadores. El historial interno y calentamiento de StockCharts siguen siendo desconocidos; no se afirma haber aislado exactamente su fórmula.

La copia local `.cache/contrast/baseline/` conserva precios de todos los instrumentos, dataset, código Python original, catálogo y SHA-256. No se publica. Para repetir sobre esa misma muestra:

```powershell
python -m pip install -r research/stockcharts/requirements.txt
python -m scripts.contrast --baseline .cache/contrast/baseline --output .cache/contrast/results
```

Se generan `REPORT.md`, `result.json`, `differences.csv` y `comparison.png`: trayectorias con ejes comunes, series X/Y por fecha, diferencias, cruces de 100, particiones y métricas de incertidumbre. El script verifica los hashes y recalcula la versión anterior contra el dataset congelado antes de comparar. No escribe en `public/` ni cambia el método activo.

## Resultado de la segunda ronda

Se amplió la búsqueda por petición posterior del usuario. Usando sólo las 36 fechas iniciales del Nasdaq, X encajó como `100*SMA(RS,10)/SMA(RS,30)` e Y como `100*X/SMA(X,9)`, sin escalas ajustadas. Nasdaq/Dow coinciden a menos de 0,005 puntos por eje.

Los conjuntos de evaluación originales ya se habían examinado; no se presentan como otra prueba ciega. La fórmula se congeló en protocol-v2.json antes de recoger las 52 semanas de NYSE Composite de confirmation-nya.csv. RMSE en la confirmación nueva: X=0,006554 / Y=0,004488, 100 % de cuadrantes evaluables y reducción >99,7 % frente al método inicial. Hay diferencias de cierres entre proveedores hasta 33,21 puntos NYSE; error máximo de coordenadas 0,0141, sin reajustes para compensarlo.

Las pruebas de integración usan tests/fixtures/weekly-prices.csv (110 semanas de cierres de Yahoo, derivadas de las copias identificadas). La copia completa de precios sigue local. El informe detallado y los gráficos están en .cache/contrast/results-v2; la web explica el trabajo en la pestaña «Qué he hecho».

La promoción afecta únicamente a índices semanales frente a GSPC. El identificador propio es relative-sma-10-30-9-v2. Es una inferencia muy fiel en esta muestra, no una especificación demostrada del código original JdK.

La evaluación de cuadrantes utiliza tolerancia numérica de 1e-9 en los límites de incertidumbre: un valor de referencia 100,01 con ±0,01 toca el eje y se excluye. Esta corrección cambia el porcentaje de la primera candidata Nasdaq de 62,5 % a 66,7 % al excluir ese punto; no cambia las decisiones ni los RMSE.

## Diagnóstico adicional de datos

La diferencia NYSE de 33,21 puntos corresponde al 30/01/2026. Al recalcular la misma SMA 10/30/9 con todos los cierres observados de StockCharts en ambos inputs, RMSE X/Y baja a 0,003069/0,003014 y el máximo por eje queda por debajo de 0,005. La fórmula no cambia y no se aplican ajustes por fecha; el cálculo público sigue usando Yahoo. El informe separa esta prueba de datos de la confirmación principal con precios Yahoo. La búsqueda de la ronda2 evaluó 10.476 estructuras X y 1.144 alternativas Y sobre el desarrollo Nasdaq.
