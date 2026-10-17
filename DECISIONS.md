# Decisiones técnicas

## Producto y presentación

Órbita es una herramienta de una pantalla para explorar índices y sectores. La navegación temporal, reproducción, escalas y tabla forman parte de la primera versión. No necesita Hugo: TypeScript/Vite y ECharts resuelven la interacción. Python prepara los datos fuera del navegador.

Diseño claro con fondos de cuadrante suaves, colores estables por instrumento, etiquetas y tabla como alternativa al gráfico. La versión móvil pliega configuración y permite desplazamiento horizontal de la tabla.

## Datos, 17/10/2026

Yahoo Finance funcionó para 18 instrumentos: cinco índices, SPY/QQQ y once sectores. Cinco años solicitados; 1.255 sesiones válidas por instrumento, hasta el 16/10/2026. Esta comprobación técnica no acredita derechos de redistribución. No hay datos inventados en la aplicación; las series sintéticas sólo se usan en pruebas.

El adaptador `DataProvider` separa descarga y cálculo. Índices con `Close`; ETFs con `Adj Close`. Referencias compatibles por grupo para no mezclar indiscriminadamente convenciones. Todo USD; sin FX. Se prepara cada benchmark permitido de antemano para no depender de una API desde GitHub Pages.

## Cierre y calendario

XNYS mediante exchange-calendars, con 90 minutos de margen de publicación. La sesión del día se excluye hasta ese momento. Agrupar el calendario completo por semana permite detectar la última sesión efectiva, incluso un jueves con viernes festivo. Sólo se usa ese cierre cuando existe en las dos series. Se intersectan fechas, sin forward-fill ni semanas provisionales.

## Indicadores

Fórmula EMA explícita del README, diario 50/20 y semanal 10/4. Cálculo causal independiente por frecuencia; cinco ventanas N de calentamiento. No son indicadores JdK ni se proclama equivalencia numérica. La cola usa N intervalos y hasta N+1 puntos. Los datos ajustados pueden ser revisados retrospectivamente por el proveedor; las pruebas de causalidad se refieren a un conjunto de precios fijo.

## Estado y escala

URL `v=1`, `g`, `tf`, `b`, `s`, `tail`, `a` y `h`; selección vacía intencional admitida. Se rechazan tickers desconocidos y referencias incompatibles. Una URL identifica la configuración con datos recientes, no la fecha histórica ni el zoom. Cambiar de frecuencia en histórico no salta a una fecha futura.

El benchmark completo se muestra en un eje independiente del selector de intervalo. Las escalas del gráfico de rotación incluyen (100,100) y las colas; los rangos se adaptan al área para mantener unidades comparables en X/Y. Hay zoom/desplazamiento manual y restablecimiento.

## Publicación y límites comprobados

Destino acordado: GitHub Pages, sin contraseña. Noindex no equivale a privacidad. Los documentos personales, cachés e históricos están excluidos de Git. La carpeta pública de datos entra en el artefacto de despliegue, preparado por Actions.

Fuentes consultadas: [README de yfinance](https://github.com/ranaroussi/yfinance), [condiciones de Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Vite](https://vite.dev/guide/static-deploy.html#github-pages) y [ayuda RRG](https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts).

No se ha verificado una licencia que autorice la redistribución pública general de los históricos Yahoo. Después de informar de esta limitación, el usuario ha pedido expresamente subir el proyecto y generar la página para su prototipo personal. Se habilita ese despliegue por su instrucción posterior, sin inventar una referencia de licencia ni afirmar que su autorización concede derechos de terceros. El adaptador permite cambiar de fuente manteniendo UI y fórmulas.

La sesión de GitHub CLI está conectada como `jordiprga`, verificada con acceso de red. Las comprobaciones sin ese acceso podían indicar erróneamente que el token era inválido. Repositorio creado: https://github.com/jordiprga/rrg-kiko. Despliegue y URL verificados: https://jordiprga.github.io/rrg-kiko/.

## Fallos y mantenimiento

Dataset escrito atómicamente; ante descarga parcial se conserva el anterior. El estado del intento se publica aparte para avisar en UI. Caché de Actions para fallback, aviso de antigüedad a los cinco días naturales y límite de 14 días antes de desplegar. Las pruebas y el build se ejecutan antes de la publicación. El workflow diario se activa con la subida al remoto.
