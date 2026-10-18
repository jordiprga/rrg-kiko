# Estudio de los componentes actuales y asignación de capital

## Cambio solicitado

El usuario sustituye el universo histórico punto en el tiempo por **todos los componentes actuales del S&P 500**. El protocolo anterior queda archivado para otra pregunta; sus requisitos de empresas excluidas y sectores históricos no bloquean este estudio. El snapshot descargado el 18/10/2026 contiene 503 valores y 500 CIK distintos. Las clases de acciones se mantienen separadas. El catálogo es reproducible con URL, fecha y SHA-256.

La pregunta es si las reglas de Órbita habrían aportado sobre el historial de estas acciones que siguen en el índice hoy. Incluye sus precios anteriores a su inclusión. El sesgo de supervivencia y el sector actual aplicado al pasado forman parte de esta definición y se muestran junto a los resultados. No equivale a una simulación del S&P 500 histórico.

## Datos y reproducción

```powershell
python -m scripts.current_universe
python -m scripts.strategies
python -u -m scripts.current_study
```

La primera orden conserva la lista y OHLCV ajustable, eventos y fuentes en `.cache/strategies/current`, fuera de Git y del sitio. Se incluyen las 503 acciones, SPY, once ETFs sectoriales, QQQ, DIA e IWM (518 series). Los ETFs son proxies; no se afirma comprar índices directamente. No se construye XLC ni XLRE antes de su creación. Una IPO empieza a producir señales cuando dispone de 50 semanas de calentamiento. Los huecos rompen la continuidad; no se rellenan para operar.

Los datos se comprueban antes de reemplazar el informe. Una descarga fallida conserva el estudio válido anterior con su fecha. Cada resultado incluye huellas de datos, catálogo, reglas y código. La web publica cálculos derivados y precios indexados; no distribuye los archivos originales OHLCV. Las condiciones del proveedor siguen siendo las de Yahoo/yfinance; la descarga gratuita no se presenta como una licencia de redistribución.

Se ha encontrado un rango inconsistente de HUBB el 05/05/2021: apertura 195,979996 y mínimo 196,210007. Se amplía el rango para abarcar la apertura y el cierre publicados, sin cambiar ninguno de los precios de ejecución ni el cierre ajustado. La modificación y los originales se conservan en `corrections`. Sólo se permite esta normalización hasta el 1 % del cierre; una anomalía mayor detiene el refresco. Afecta potencialmente ATR y excursión, no se oculta como dato original.

## Dos experimentos separados

**Entradas y salidas.** Las cuatro entradas y sus confirmaciones de uno/dos periodos se comparan frente a SPY y al ETF del sector actual, con/sin sector Líder y volumen relativo 1,2. Se comparan quince salidas registradas más controles de 4 y 52 semanas: 1.088 variantes. Asignación idéntica: equiponderar todas las posiciones activas cada apertura, con coste de entrada, salida y rebalanceo. Una posición por acción; las señales durante una operación no añaden compras. Los horizontes temporales se miden en semanas de calendario. Máximo 52 semanas.

**Carteras con capital limitado.** Familia congelada de 144 políticas: cuatro entradas × tres salidas (13 semanas, trailing 15 % + órbita, ATR22 × 3 + órbita) × tres asignaciones × filtro sectorial sí/no × filtro de índices sí/no. Señales semanales frente a SPY y confirmación inmediata. No se optimiza una rejilla ilimitada de parámetros ni se introduce volumen en esta familia después de ver resultados.

Las asignaciones son 20 posiciones equiponderadas, 20 con pesos inversos a volatilidad diaria de 60 sesiones conocidas, o 10 posiciones con prioridad de fuerza. Las señales nuevas que coinciden se ordenan por X+Y, con desempate por ticker. No se reemplazan posiciones existentes sólo por un ranking posterior. Cada posición conserva la regla de salida con la que nació. Máximos de 5 % por acción (20 plazas) o 10 % (10 plazas), y 25 % por sector al rebalancear. Los pesos se recortan, sin renormalizar por encima del límite; el resto queda en efectivo. Entre rebalanceos los pesos pueden derivar.

Se reequilibra al abrir la primera sesión de cada semana y en entradas/salidas. Sin apalancamiento ni cortos. El filtro de índices exige que SPY esté por encima de SMA200 y al menos dos de QQQ/DIA/IWM también, calculado al cierre anterior; si falla, liquida a la apertura posterior. El cambio de política anual conserva salidas iniciales, pero el filtro de mercado y límites de asignación son globales de la política vigente.

Las órdenes son simuladas. Señal al cierre de semana completada y compra en la apertura siguiente. Los trailing se activan al cierre diario y venden en apertura posterior; no prometen un precio intradía. Dividendos contabilizados una vez mediante ajustes coherentes de OHLC. Coste principal 10 pb por lado y por importe negociado en rebalanceos; sensibilidad 5 y 25 pb. Sin impuestos, remuneración del efectivo, impacto dependiente del tamaño ni lotes enteros. El capital inicial sólo escala la curva, no demuestra capacidad para ejecutar esa cantidad.

## Separación temporal y selección

1. **In sample 2010–2018.** Se conservan tres candidatas con mayor mediana de Sharpe anual en 2016–2018. No se consulta test.
2. **Validación 2019–2022.** Entre esas tres se elige por Sharpe de validación; desempate por menor caída y rotación. La seleccionada queda identificada explícitamente.
3. **Out of sample 2023–última sesión cerrada.** Se calcula con reglas fijadas y capital inicial nuevo, sin arrastrar posiciones abiertas en el periodo anterior. Ver una alternativa mejor en test no permite sustituir automáticamente el modelo elegido.

Cada tramo empieza en efectivo y sólo admite señales originadas en ese tramo; los indicadores pueden usar historia anterior para calentamiento. Las operaciones cuya salida queda fuera del tramo se valoran a mercado en la cartera y se registran como abiertas en la estadística del tramo. No se transforman en retorno cero ni se borran.

Además hay una cartera **walk-forward** distinta: para cada año desde 2015, sólo se consideran los cinco años anteriores; mediana de los Sharpes de los tres últimos años, tolerancia 0,05 y desempate por menor caída. Las valoraciones de posiciones abiertas al cierre de entrenamiento son información conocida, nunca se introduce su desenlace posterior en la selección. El nuevo modelo controla las compras siguientes y las posiciones existentes mantienen sus salidas. Sus pesos pueden adaptarse a la nueva política global. Se conservan todas las elecciones y fechas máximas de información.

Todo es validación temporal **retrospectiva** sobre un universo actual. Ni el corte 2023 ni el walk-forward convierten una hipótesis ya inspirada por episodios conocidos en evidencia prospectiva independiente. Se conservan todas las variantes, sin presentar el mejor test como si hubiese sido elegido de antemano.

## Métricas y controles

CAGR sobre tiempo de calendario y capital real acumulado, Sharpe diario anualizado √252 con tipo libre de riesgo cero, Sortino con RMS de retornos diarios negativos, volatilidad, Calmar, caída máxima, rentabilidad por año, exposición, posiciones medias y rotación. Las operaciones cerradas tienen tasa de acierto, mediana, distribución y duración; las abiertas y sin datos tienen recuentos separados. Nunca se encadenan operaciones solapadas para fabricar CAGR.

Los controles son SPY en exactamente las mismas fechas y una cartera equiponderada de los mismos componentes actuales, con 252 sesiones de historial mínimo y los mismos costes diarios de rebalanceo. La segunda comparte el sesgo del universo y permite comprobar si el valor lo aportan las señales o la selección retrospectiva de supervivientes. No es el índice S&P 500 equiponderado histórico.

La entrada se estudia también a 13 semanas mediante exceso sobre SPY en las mismas fechas; remuestreo de bloques de calendario de 52 semanas, 2.000 réplicas y corrección de Holm sobre las ocho comparaciones principales (cuatro reglas × dos referencias). Los resultados de cada tramo usan únicamente operaciones completadas dentro de él; los desenlaces que atraviesan su frontera se purgan de esa inferencia. Los filtros y variantes restantes son exploratorios. Una asociación significativa en este universo no elimina sus sesgos ni garantiza rentabilidad futura.

Las métricas usan todas las sesiones. Sólo las curvas que viajan a la web se muestrean cada cinco sesiones para ahorrar transferencia; el detalle de cada cartera se carga al seleccionarla. Se muestran asignaciones mensuales y la última disponible, con fecha explícita.

Se resolvió además la única sesión diaria ausente del conjunto: FISV, 12/11/2025. El traslado FI → FISV está documentado por Fiserv y Nasdaq. La barra diaria completa se obtuvo de Quiver; tres sesiones vecinas coinciden en OHLC a céntimos. Se descartó reconstruirla desde barras horarias de Yahoo porque omiten subastas y no reproducen apertura/cierre/volumen diario. La fuente, fecha y hash de evidencia se conservan en la caché y en las correcciones del informe. No se interpoló ni se eliminó Fiserv del universo.

Referencias del traslado Fiserv: [anuncio del emisor](https://investors.fiserv.com/news-releases/news-release-details/fiserv-announces-transfer-stock-exchange-listing-nasdaq), [aviso Nasdaq DTN2025-32](https://www.nasdaqtrader.com/TraderNews.aspx?id=DTN2025-32) y [barra diaria publicada por Quiver](https://www.quiverquant.com/stock/FISV/historical-prices/).
