# Órbita · rotación relativa

Explorador de fuerza relativa para índices y sectores estadounidenses. Diario/semanal, cuatro cuadrantes, colas de 1–30 periodos, reproducción histórica, zoom, tabla y enlaces compartibles.

**[Abrir Órbita](https://jordiprga.github.io/rrg-kiko/)**

## Ejecutar

Requisitos: Node.js 24, pnpm 11.25.0 y Python 3.11. Se recomienda crear un entorno virtual de Python.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pnpm install --frozen-lockfile
python -m scripts.market
pnpm dev
```

Abrir la dirección local que imprime Vite. Si falta `pnpm`, instalarlo desde su distribución oficial. Los datos sólo se descargan con el comando de ingesta, nunca desde el navegador.

```powershell
python -m pytest tests -q
pnpm test
pnpm build
pnpm preview
```

`python -m scripts.market --offline` recalcula usando `.cache/prices/` sin descargar. La caché debe contener el catálogo y la última sesión esperada. `python -m scripts.validate_data` comprueba un dataset para publicación.

## Usar y compartir

- Inicio: cuatro índices frente al S&P 500, semanal, 17 periodos. El conjunto de sectores abre seis ETFs frente a SPY.
- Cambiar diario/semanal mantiene la selección. Desde una fecha histórica se escoge el último periodo cerrado que no la supere.
- Arrastrar la ventana bajo el benchmark o usar el selector de fecha. Los botones y las flechas izquierda/derecha recorren periodos; «Reproducir» anima y «Última sesión» vuelve al presente. La reproducción se pausa al ocultar la pestaña.
- «Ajustar» encuadra las colas actuales; «Histórico» encuadra todo el histórico de los activos visibles; «Centrar» sitúa (100,100) en el centro. «Fijar ajuste» recalcula el modo elegido con cada cambio; desmarcarlo conserva la escala. Ratón/pellizco para zoom; arrastrar para desplazar.
- Marcar/desmarcar en el panel añade o quita instrumentos. Las casillas de la tabla sólo controlan visibilidad. Pulsar el nombre de una fila resalta su trayectoria; repetir quita el resaltado.
- «Copiar enlace» guarda universo, referencia, activos, periodicidad, cola, flechas y activos ocultos en la URL. Incluye alternativa manual si el navegador deniega el portapapeles. No depende de almacenamiento local.
- El enlace siempre carga el último periodo disponible del dataset, no la fecha histórica explorada.
- La cola mide intervalos: 17 periodos necesitan hasta 18 observaciones. En el inicio del histórico se dibujan sólo las observaciones disponibles.

## Catálogo y precios

Histórico de cinco años, con todos los instrumentos en USD:

- Índices de precio: `^GSPC`, `^IXIC`, `^NDX`, `^DJI`, `^RUT`. Referencias S&P 500 o Nasdaq 100.
- Sectores: `XLK`, `XLF`, `XLE`, `XLI`, `XLV`, `XLY`, `XLP`, `XLU`, `XLB`, `XLRE`, `XLC`. Referencias `SPY` o `QQQ`.
- `SPY` y `QQQ` son ETFs proxy y se identifican como tales. Todos los instrumentos están en USD.

Editar `config/catalog.json` para añadir instrumentos de la misma familia. Incluir ID único, ticker del proveedor, nombre, tipo, grupo, mercado y moneda; `proxyOf` cuando corresponda. Añadir su ID a `defaults` si debe aparecer de inicio. Ejecutar ingesta, pruebas y validación antes de publicar; no basta con editar el catálogo del navegador. No se admite aún búsqueda libre de cualquier ticker en tiempo real.

Índices: `Close`. ETFs: `Adj Close`, ajustado por dividendos y splits. Los grupos no permiten cruzar ambas convenciones de benchmark. Una serie ajustada puede revisarse tras eventos corporativos del proveedor.

## Matemática

```text
RS(t) = precio_activo(t) / precio_referencia(t)
X(t) = 100 × RS(t) / EMA(RS,N)(t)
Y(t) = 100 × X(t) / EMA(X,M)(t)
```

EMA causal (`adjust=False`), inicializada con la primera observación. Se descartan cinco ventanas N: 250 sesiones diarias o 50 semanas. Diario N=50/M=20; semanal N=10/M=4. Los valores **no son JdK RS-Ratio ni JdK RS-Momentum**, y no se afirma equivalencia con StockCharts. Sobre un eje se indica «En el eje» en vez de asignar un cuadrante arbitrario.

El calendario XNYS determina cierres, festivos y sesiones reducidas. Se aplica una demora prudente de 90 minutos tras el cierre. La semana sólo se considera completa al cerrar su última sesión programada; se requiere que esa sesión exista en ambas series. No se rellenan precios faltantes.

## Actualización y tolerancia a fallos

`python -m scripts.market` descarga, valida y reemplaza el dataset de forma atómica. Tres intentos por instrumento. Con un dataset previo, cualquier descarga parcial conserva íntegra la copia anterior. `refresh-status.json` registra el fallo; la interfaz lo muestra y advierte también al superar cinco días naturales desde la última sesión.

El workflow `Refresh market data and deploy Pages` está preparado para lunes–viernes a las **23:35 UTC** (18:35/19:35 de Nueva York según estación), y disparo manual. Recupera la última copia válida desde la caché de Actions; si falla el refresco, puede publicar esa copia con aviso. No despliega datos de más de 14 días ni una pantalla vacía. Si el workflow falla antes de desplegar, la publicación anterior sigue disponible.

Actions puede retrasarse y GitHub puede desactivar crons de repositorios públicos tras 60 días sin actividad. Para forzar una ejecución: Actions → «Refresh market data and deploy Pages» → «Run workflow». No es tiempo real ni tiene garantía de horario.

## Fuente y alcance

Datos de [Yahoo Finance](https://finance.yahoo.com/) mediante [yfinance](https://github.com/ranaroussi/yfinance), sujetos a las condiciones del proveedor. Indicadores independientes; no constituye recomendación de inversión.

La aplicación utiliza TypeScript, Vite y ECharts; Python prepara los históricos. Se aloja en GitHub Pages y se actualiza mediante GitHub Actions.
