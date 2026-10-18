# Estrategias de Kiko

## Estudio activo: componentes actuales y capital simulado

El usuario ha cambiado expresamente el universo: se incluyen **todos los componentes actuales**, sin exigir empresas ya excluidas. El estudio semanal calcula CAGR, Sharpe, Sortino, caída máxima y carteras con límites, efectivo y costes. Se separan entrenamiento 2010–2018, validación 2019–2022 y prueba posterior desde 2023; además se calcula walk-forward. Reglas, 144 políticas de asignación y límites: [CURRENT_UNIVERSE.md](CURRENT_UNIVERSE.md). El protocolo histórico descrito debajo queda como archivo de la pregunta anterior, sin bloquear el estudio actual.

El objetivo es evaluar cuatro entradas (giro de momentum, giro de fuerza, Rezagado → Mejorando y Mejorando → Líder), manteniendo separados el estudio de eventos y una cartera mecánica de referencia. El protocolo está en `protocol.json`; el motor no recalibra la fórmula RRG para mejorar resultados de trading.

## Estado comprobado el 18/10/2026

La pestaña Estrategias funciona con ocho casos reales: cuatro índices, diario y semanal, frente al S&P 500. Incluye señales inmediatas/confirmadas, recorrido sincronizado, futuro oculto hasta revelarlo, percentiles contemporáneos, nueve zonas exploratorias y enlaces compartibles. Los ejemplos de índices describen cierres; no simulan operaciones netas de acciones.

**El estudio completo del S&P 500 no es evaluable con los datos reunidos.** No se han publicado estadísticas de una muestra de supervivientes. La descarga real de [fja05680/sp500](https://github.com/fja05680/sp500) produjo 1.262 intervalos, 848 tickers con intervalos posteriores a 2010 y 363 intervalos terminados; último cambio incluido: 18/08/2026. Un intervalo terminado puede representar un cambio de símbolo, no una baja bursátil. La recopilación tampoco aporta todos los sectores históricos, identidades estables ni liquidaciones. Su autor documenta limitaciones de reconstrucción y de Yahoo; MIT para un repositorio no demuestra todos los derechos de sus datos de origen.

La prueba real de Yahoo entregó OHLCV, ajustes y eventos de SPY, XLK y AAPL desde el 02/01/2009 hasta el 16/10/2026 (4.475 sesiones cada una). No entregó AABA ni ABKFQ en esta comprobación. Se registra un fallo de descarga, no una demostración de inexistencia permanente del histórico. Los archivos y respuestas quedan en `.cache/strategies/sources/`, excluidos de Git y del sitio. [yfinance](https://ranaroussi.github.io/yfinance/) remite a las condiciones del proveedor para el uso de los datos.

[N-PORT de la SEC](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets) sirve para contrastar carteras desde 2019 y su disponibilidad pública. No representa automáticamente el universo diario del índice ni toda la clasificación sectorial histórica. Faltan evidencia primaria contrastada para el libro completo, los sectores históricos y los resultados económicos de las bajas. Presupuesto cero; no se contrata una fuente ni se sustituye este requisito por la lista actual.

## Preparación y ejecución

```powershell
# Evidencia candidata, con hash del archivo original; no certifica un universo.
python -m scripts.strategy_sources
python -m scripts.strategy_sources --tickers SPY XLK AAPL AABA ABKFQ

# Genera cobertura y ejemplos reales desde public/data/market.json.
python -m scripts.strategies

# Evalúa únicamente un conjunto privado que supere la auditoría.
python -m scripts.strategies --input .cache/strategies/input.json

python -m pytest tests -q
pnpm test
pnpm build
pnpm test:e2e
```

El último comando usa Edge instalado en Windows y Chromium de Playwright en Linux. En Linux se prepara con `pnpm exec playwright install --with-deps chromium`. El servidor de QA copia el build bajo `.cache/preview/rrg-kiko/` y comprueba la subruta real. Las capturas se guardan en `test-results/`, ignorado por Git. No se requieren credenciales para la interfaz.

## Contrato privado, versión 1

`scripts/strategy_data.py` define los contratos y `load_research` lee el JSON. No se aceptan como equivalentes un ticker, una empresa y una clase de acción.

| Campo superior | Contenido |
| --- | --- |
| `version` | `1` |
| `start`, `end` | Intervalo admitido de evaluación, ISO, con fin en sesión cerrada. Incluir antes de `start` las barras de calentamiento disponibles. |
| `securities` | Objetos con `id` estable, `name`, `ticker` descriptivo y `delisted`. No reutilizar una identidad al reciclarse un ticker. |
| `memberships` | `security_id`, `start` inclusivo, `end` exclusivo o null, `available_at` UTC y `source_id`. |
| `sectors` | Los campos de pertenencia, más `sector` y `etf`; usar los intervalos efectivos y disponibilidad histórica. |
| `bars` | Diccionario por identidad estable y referencias (`SPY`, ETFs): listas ordenadas de barras diarias. |
| `delistings` | `security_id`, `last_trading_date`, `settlement_date`, `settlement_price` bruto (cero permitido), `available_at`, `source_id`. |
| `sources` | `id`, URL HTTPS, `retrieved_at`, `content_hash` SHA-256, `publication_allowed`, `verified`, `role`. |
| `universe_ledger` | Una entrada por sesión cerrada: `date`, todos los `members`, `source_id`, `evidence_hash` coincidente con la fuente primaria. |

Cada barra contiene `date`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume` o null, `volume_basis` (`raw` o `split-adjusted`), `available_at` UTC, `source_id`, `dividend` y `split` (1 si no hay split). El ajuste de OHLC es `adjusted_close/close`. Las distribuciones se incluyen una vez mediante los precios ajustados; no se suman otra vez como efectivo. El volumen se normaliza exclusivamente por splits y únicamente si llega sin ajustar. Se exige declarar su base para evitar ajustar dos veces series ya ajustadas, como las que normalmente entrega Yahoo; sigue pendiente el contraste de anomalías del proveedor. Un volumen con base desconocida no supera la auditoría. Las rentabilidades corresponden a una convención de reinversión ajustada y los precios de ejecución mostrados usan esa misma escala.

`verified` es una declaración de contraste respaldada por el archivo de evidencias: no se obtiene automáticamente por una descarga exitosa. Pertenencias, sectores y liquidaciones requieren fuente `role=primary`. Las barras pueden tener `role=market-data`, también contrastada. Conservar las evidencias originales y sus hashes junto al conjunto privado; la auditoría comprueba consistencia y cobertura, no demuestra la veracidad de una declaración introducida manualmente. Los candidatos descargados permanecen `verified=false` y `publication_allowed=false`.

El libro no puede representar una lista pequeña como todo el S&P 500: exige al menos 480 miembros por sesión, sin imponer exactamente 500 por las clases de acciones. Se comprueba que todas las identidades del libro coincidan con los intervalos, tengan sector conocido y barras de cada sesión junto a SPY y el ETF. Las sesiones sin barras se consideran incidencias pendientes de resolver. No se rellenan precios para operar ni se excluyen silenciosamente suspensiones o IPOs. Un intervalo que no satisface la cobertura no se evalúa. Un periodo más corto debe fijarse por cobertura antes de observar retornos; los mínimos estadísticos siguen vigentes.

La descarga candidata de Yahoo conserva OHLCV y eventos, pero su disponibilidad EOD histórica se aproxima con cierre XNYS + 90 minutos. Es un supuesto explícito y no un archivo del instante real de publicación. No acredita el requisito de disponibilidad histórica por sí solo.

## Cálculo, operaciones y evaluación

- Semanal: SMA 10/30/9, descarte inicial 50 semanas. Diario: EMA 50/20, 250 sesiones. La serie se reindexa al calendario antes del cálculo; las ventanas no comprimen huecos. La EMA reinicia su calentamiento tras un hueco.
- Giros: cambio de pendiente no positiva a positiva, permaneciendo en Rezagado. Confirmar dos periodos registra la fecha posterior; no mueve una señal hacia atrás. Los puntos neutros permiten un único cruce; una discontinuidad reinicia la detección.
- Sectores: se utiliza la última semana completada conocida para el filtro Líder frente a SPY. La referencia sectorial cambia con el intervalo histórico de clasificación y reinicia la continuidad de señales.
- Volumen: media de las 20 sesiones anteriores o diez medias semanales de volumen por sesión. Se excluye el periodo actual de la base. Si falta volumen, se conserva null.
- Percentiles: rangos medios para empates sobre el grupo elegible de esa fecha y benchmark; frente al sector se separa cada ETF. Las nueve zonas son terciles exploratorios. El futuro no participa en su clasificación.
- Entradas y salidas se ejecutan en la primera apertura posterior a la información disponible. Un cierre que alcanza horizonte o trailing desencadena una ejecución en la siguiente apertura. No se supone ejecución intradía al umbral del stop. El plazo máximo de 52 semanas se verifica al cierre y se ejecuta en esa apertura posterior.
- ATR de Wilder de 22 sesiones, inicializado por la media de los primeros 22 true ranges. Cada trailing es monótono. Se comparan 15 salidas registradas y cuatro horizontes de entrada. En empate de eventos se conserva un motivo determinista, sin mejorar el precio de salida.
- El estudio de eventos conserva señales solapadas; la simulación por estrategia registra las entradas suprimidas mientras existe posición. Los estados pending/open/missing-data/suppressed no se convierten en cero ni en operaciones cerradas. Los peer controls utilizan el mismo sector y fecha y conservan la falta de resultado cuando una liquidación no puede resolverse.
- La cartera de referencia equipondera las posiciones activas en cada apertura, incluye la deriva de pesos, coste del rebalanceo y liquidaciones. Tipo libre de riesgo y efectivo: cero. Una valoración sin resolver invalida la curva, no elimina el valor.
- Cada año exterior usa los cinco anteriores. Se puntúan tres validaciones anuales interiores, con reglas fijas; únicamente operaciones enteramente dentro de cada validación. Se selecciona la mediana de Sharpe; tolerancia 0,05, después menor caída y rotación. La selección futura no modifica la salida de una posición ya abierta.
- Se registran todas las variantes: 128 combinaciones de entrada/referencia/frecuencia/confirmación/filtros, con las familias de salidas y horizontes fijadas. Las ocho comparaciones semanales principales (cuatro entradas × dos referencias, sin filtros y confirmación inmediata) reciben Holm. El resto queda exploratorio.
- Incertidumbre: 2.000 réplicas reproducibles de bloques circulares de calendario de 52 semanas, incluyendo semanas sin señales. Se conservan los cocientes sumas/recuentos para respetar agrupación temporal. Sin dos bloques no se publica intervalo. La conclusión favorable requiere cinco años completos de evaluación, cien operaciones, treinta fechas de entrada, exceso neto positivo con IC y Holm, y resultado positivo en los tres escenarios de costes. Estos mínimos no garantizan una precisión concreta.

## Reproducibilidad, prospectivo y publicación

Cada ejecución conserva hashes del input, protocolo y código de cálculo. Los informes privados están en `.cache/strategies/runs/`; el protocolo se conserva por huella. Las señales históricas conocidas de RUT son ilustraciones. Todo el walk-forward histórico es retrospectivo: no se declara un holdout ciego a partir de una hipótesis inspirada por esos datos.

El registro prospectivo es append-only y encadenado por hashes; detecta alteraciones y deduplica por señal y protocolo. Sólo incorpora señales posteriores a la congelación y observadas con un retraso máximo de cuatro días. La disponibilidad de ejecución incluye el instante real de registro: ejecutar hoy una tarea atrasada no permite una entrada de ayer. La evaluación prospectiva utiliza las señales registradas, incluidas las que una revisión posterior del proveedor borrase del cálculo. Sus precios y resultados identifican el snapshot usado; las revisiones del proveedor no son un archivo histórico de cotizaciones originalmente publicadas.

Los detalles de acciones sólo se publican si todas las fuentes importadas tienen permiso explícito documentado. En caso contrario, los resultados quedan privados y la web muestra ese estado. El manifiesto es el último archivo reemplazado; un refresco inválido conserva el estudio válido anterior y escribe un aviso separado. Las rutas de datos incluyen hashes y cargan por caso; los precios privados no entran en `dist`.

GitHub Actions genera automáticamente la cobertura y los casos del catálogo existente antes del build y ejecuta QA en escritorio/móvil. No dispone todavía de un conjunto histórico gratuito de acciones certificado; no se anuncia una actualización automática de ese universo. El registro prospectivo se conserva en una caché separada de Actions; una caché no sustituye una copia de archivo duradera y su pérdida debe documentarse como interrupción de continuidad.
