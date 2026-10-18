# Contraste semanal con StockCharts

Investigación del 18/10/2026. No forma parte del directorio público de la web.

`observations.csv` conserva 52 fechas efectivas por activo, desde 24/10/2025 hasta 16/10/2026: `$COMPQ`/`^IXIC` y `$INDU`/`^DJI`, benchmark `$SPX`/`^GSPC`. Cada fila incluye cierres, fuente y precisión. `source.json` describe la inversión de las coordenadas SVG, sus límites y un ejemplo de calibración. `read-visible-svg.js` conserva el procedimiento de lectura de los elementos dibujados. No se consultan variables internas de la web.

Los valores son reconstrucciones del SVG, con incertidumbre conservadora ±0,01 por eje. No son valores de un tooltip numérico ni estimaciones de píxeles de las capturas. En los primeros seis puntos del Dow se usaron los círculos de cola de la ventana de 30 terminada el 22/05/2026: las cabezas se fijaban al borde de la escala visible y daban coordenadas falsas. El benchmark y los precios proceden de los textos de la web.

Se comprobó una cola de 30 y una de 10: N círculos pequeños más la cabeza actual. Las fechas festivas se guardan con la última sesión real, no con un viernes inventado.

`protocol.json` fija el reparto cronológico y los criterios antes de la primera búsqueda. Nasdaq: 36 fechas de ajuste, 16 reservadas. Todo Dow reservado. Se probaron 5.160 combinaciones EMA con escalas positivas centradas en 100, estimadas exclusivamente en el ajuste. No se amplió la búsqueda después de ver la evaluación.

La mejor candidata usa suavizado 10, referencia 24, momentum 13 y escalas X=0,9271679043 / Y=1,0855665210. Alcanza los cuadrantes y el sentido del último tramo de ambos casos de Kiko, pero **no supera la validación independiente**:

| Evaluación | RMSE X/Y actual | RMSE X/Y candidata | Cuadrantes candidata |
|---|---|---|---|
| Nasdaq reservado | 2,071 / 1,201 | 0,814 / 0,475 | 62,5 % |
| Dow completo | 1,724 / 1,108 | 0,656 / 0,392 | 72,5 % |

Se conserva `relative-ema-v1`. El umbral es 0,20 por eje y 95 % de cuadrantes. Suavizado y momentum óptimos están en el límite de la búsqueda; ampliar el espacio sería otro experimento, con nueva evaluación independiente para no reutilizar estos resultados como ajuste.

Los cierres casi coinciden: error absoluto máximo S&P 500=0,0002344; Dow=0,001875; Nasdaq=0,0109375. No explican por sí solos discrepancias de varios puntos en los indicadores. El historial interno y calentamiento de StockCharts siguen siendo desconocidos; no se afirma haber aislado exactamente su fórmula.

La copia local `.cache/contrast/baseline/` conserva precios de todos los instrumentos, dataset, código Python original, catálogo y SHA-256. No se publica. Para repetir sobre esa misma muestra:

```powershell
python -m pip install -r research/stockcharts/requirements.txt
python -m scripts.contrast --baseline .cache/contrast/baseline --output .cache/contrast/results
```

Se generan `REPORT.md`, `result.json`, `differences.csv` y `comparison.png`: trayectorias con ejes comunes, series X/Y por fecha, diferencias, cruces de 100, particiones y métricas de incertidumbre. El script verifica los hashes y recalcula la versión anterior contra el dataset congelado antes de comparar. No escribe en `public/` ni cambia el método activo.
