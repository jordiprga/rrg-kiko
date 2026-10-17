import './style.css';
import { initChart, rotationOptions, benchmarkOptions, palette, type PlotAsset } from './charts';
import { defaults, parseState, serialize, trail, indexAtOrBefore, scaleBounds, quadrant, quadrants,
  validateDataset, type Dataset, type State, type Group, type Timeframe, type Point } from './model';

const root = document.querySelector<HTMLDivElement>('#app')!;
const esc = (s: string) => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const icon = (name: string) => {
  const paths: Record<string, string> = {
    share: '<path d="M8 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-7M16 3h5v5M21 3l-9 9"/>',
    play: '<path d="m8 5 11 7-11 7z"/>', pause: '<path d="M8 5v14M16 5v14"/>',
    left: '<path d="m14 6-6 6 6 6"/>', right: '<path d="m10 6 6 6-6 6"/>',
    reset: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    orbit: '<ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-40 12 12)"/><circle cx="18" cy="5" r="2.5" fill="currentColor" stroke="none"/>',
  };
  return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? ''}</svg>`;
};
const fmt = (value: number, digits = 2) => value.toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const formatDate = (date: string) => new Date(date + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });

async function boot() {
  const response = await fetch(`${import.meta.env.BASE_URL}data/market.json`, { cache: 'no-cache' });
  if (!response.ok) throw new Error('No se han podido cargar los históricos. Reintenta en unos minutos. Si estás ejecutando el proyecto localmente, prepara los datos con «python -m scripts.market».');
  const data: Dataset = validateDataset(await response.json());
  let refreshFailed = false;
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}data/refresh-status.json`, { cache: 'no-cache' });
    if (response.ok) refreshFailed = (await response.json()).ok === false;
  } catch { /* The dataset includes its own age even without a refresh-status file. */ }
  let state: State = parseState(location.search, data);
  let end = 0, highlighted: string | null = null, playing = false, timer: ReturnType<typeof setInterval> | undefined;
  let scaleMode: 'fit' | 'max' | 'center' = 'center', lock = true, bounds: number[] | undefined;
  let sortKey = 'name', ascending = true;
  const catalog = new Map(data.catalog.map(i => [i.id, i]));
  const color = (id: string) => palette[data.catalog.findIndex(i => i.id === id) % palette.length];
  const instrument = (id: string) => catalog.get(id)!;
  const view = () => data.views[state.benchmark][state.tf];
  const currentDate = () => view().benchmark[end][0];
  const instrumentLabel = (id: string) => `${instrument(id).name}${instrument(id).proxyOf ? ' · ETF proxy' : ''}`;
  const futureClock = Date.now() < Date.parse(data.generatedAt) - 86_400_000;
  const stale = Date.now() - Date.parse(data.latestSession + 'T21:30:00Z') > 5 * 86_400_000;
  const exampleView = data.views.GSPC?.weekly;
  const examplePoint = exampleView?.assets.IXIC?.at(-1);
  const exampleReference = examplePoint ? exampleView?.benchmark.find(p => p[0] === examplePoint[0]) : undefined;
  const realExample = examplePoint && exampleReference ? `<div class="kiko-example"><strong>Un punto real que hemos podido calcular</strong><p>Nasdaq Composite frente al S&P 500 · semanal · ${formatDate(examplePoint[0])}.<br>Cierre Nasdaq: ${fmt(examplePoint[3])} · cierre S&P 500: ${fmt(exampleReference[1])}.<br>RS = ${fmt(examplePoint[3] / exampleReference[1], 5)}.<br>Con sus medias históricas, el resultado es <strong>X=${fmt(examplePoint[1])}, Y=${fmt(examplePoint[2])}</strong> → ${quadrants[quadrant(examplePoint[1], examplePoint[2])].name}.</p><p>Estas coordenadas salen de nuestra fórmula y del dataset cargado; no son valores obtenidos de StockCharts. El ejemplo se actualiza al actualizar los datos.</p></div>` : '';

  const methodologyMarkup = `
        <details class="method-card top-method" id="methodology" open>
          <summary>Kiko, aquí te explico lo que quieres entender jeje <span class="kiko-badge">Empieza por aquí 👀</span><span aria-hidden="true">＋</span></summary>
          <div class="method-content">
            <section class="kiko-explainer" id="para-kiko" aria-labelledby="kiko-heading">
              <h3 id="kiko-heading">Cómo investigué la referencia y qué calcula esta web</h3>
              <a class="kiko-video" href="https://www.youtube.com/watch?v=DLzxrzFCyOs" target="_blank" rel="noopener noreferrer"><span aria-hidden="true">▶</span><span>Primero, abre este vídeo<strong>Una introducción imprescindible 😉</strong></span><span aria-hidden="true">↗</span></a>
              <p class="kiko-intro">Ahora sí, Kiko: preguntabas si investigué cómo colocan un punto en la web que pasaste y qué operación hacemos entre el activo y la referencia. Esto es lo que pude comprobar y lo que hemos implementado.</p>
              <h4>Cómo exploré la web que pasaste</h4>
              <p>Abrí el <a href="https://stockcharts.com/freecharts/rrg/?tailLength=17" target="_blank" rel="noopener noreferrer">RRG de StockCharts</a> y revisé la vista gratuita: los cuatro cuadrantes, la barra de controles, la tabla de símbolos y el panel «Quick Tips». Después contrasté su navegación con la <a href="https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts" target="_blank" rel="noopener noreferrer">ayuda oficial</a>: cola, flechas, animación, ventana temporal del benchmark, zoom y botones Fit/Max/Center.</p>
              <p>La vista gratuita está limitada a un conjunto semanal fijo. Las opciones de configuración para miembros las estudié en su documentación; no accedí a una cuenta de pago. Esa revisión sirvió para reconstruir la interacción y añadir lo que pediste: diario/semanal, selección de activos y enlace permanente.</p>
              <h4>Qué averigüé sobre el cálculo original</h4>
              <p>Revisé también la <a href="https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/rrg-relative-strength" target="_blank" rel="noopener noreferrer">documentación de sus indicadores</a>. StockCharts usa <strong>JdK RS-Ratio</strong> en horizontal, para representar la tendencia de fuerza relativa, y <strong>JdK RS-Momentum</strong> en vertical, para el momentum del primer indicador. Ambos están normalizados alrededor de 100.</p>
              <p><strong>En las páginas consultadas no encontré una especificación completa del algoritmo con la que reproducir y verificar sus valores.</strong> Conocer el concepto y los nombres de los ejes no basta para deducir su fórmula exacta. Por eso no hemos calculado los JdK originales: implementamos una alternativa explícita basada en medias exponenciales. Tampoco hemos validado equivalencia numérica comparando sus coordenadas con las nuestras.</p>
              <h4>Qué hemos podido calcular con datos reales</h4>
              <p>Descargamos cinco años de cierres de Yahoo Finance para los índices y ETFs del catálogo. A partir del histórico de cada activo y su benchmark, calculamos series diarias y semanales propias de fuerza relativa y momentum. No copiamos puntos de StockCharts ni generamos trayectorias simuladas. La secuencia de cálculo es ésta:</p>
              <h4>1. Comparamos el activo con la referencia</h4>
              <p>En cada fecha dividimos el cierre del activo por el cierre del benchmark. Ese cociente se llama fuerza relativa, o RS.</p>
              <p><code>RS = precio del activo / precio del benchmark</code></p>
              <p>Si el activo lo hace mejor que la referencia, RS sube; si lo hace peor, baja. Puede mejorar aunque ambos caigan, si el activo cae menos.</p>
              <h4>2. Calculamos la posición horizontal: X</h4>
              <p>Comparamos RS con su media móvil exponencial (EMA). Esta media da más peso a las observaciones recientes. Multiplicamos por 100 para situar la referencia en 100.</p>
              <p><code>X = 100 × RS / EMA(RS, N)</code></p>
              <p><strong>X &gt; 100:</strong> el cociente activo/benchmark está por encima de su media reciente. <strong>X &lt; 100:</strong> está por debajo. X=102 significa un 2 % sobre esa media; no significa que el activo haya superado al índice en un 2 % durante un plazo concreto.</p>
              <h4>3. Calculamos la posición vertical: Y</h4>
              <p>Comparamos X con su propia media exponencial para representar su momentum relativo.</p>
              <p><code>Y = 100 × X / EMA(X, M)</code></p>
              <p><strong>Y &gt; 100:</strong> X está por encima de su media reciente. <strong>Y &lt; 100:</strong> está por debajo. No es la rentabilidad del activo ni una derivada instantánea.</p>
              ${realExample}
              <div class="kiko-example"><strong>Un ejemplo con números inventados, sólo para entenderlo</strong><p>Activo: 102 · benchmark: 5.000 → RS=0,0204.<br>Si EMA(RS)=0,0200 → X=102.<br>Si EMA(X)=101 → Y≈100,99.<br>El punto (102; 100,99) cae en <strong>Líder</strong>: ambos indicadores superan 100.</p></div>
              <h4>4. Unimos los puntos para dibujar la cola</h4>
              <p>Cada sesión o semana produce un punto (X,Y). La cola conecta esos puntos en orden temporal y termina en la fecha explorada. Una cola de 17 periodos utiliza hasta 18 observaciones. Cambiar su longitud modifica el recorrido visible, no la fórmula ni el punto final.</p>
              <h4>¿Qué parámetros usamos?</h4>
              <p><strong>Diario:</strong> N=50 sesiones y M=20 sesiones. <strong>Semanal:</strong> N=10 semanas y M=4 semanas. Son parámetros elegidos para esta implementación, no los oficiales de StockCharts. El semanal se calcula con su propia serie de cierres semanales; no es una muestra del indicador diario.</p>
              <h4>¿Es exactamente el RRG de StockCharts?</h4>
              <p><strong>La navegación toma esa web como referencia; el motor matemático es independiente.</strong> Lo comprobado es que nuestra implementación calcula la fórmula descrita con históricos reales. No se ha demostrado que coloque cada activo en el mismo punto o cuadrante que StockCharts. También pueden influir las diferencias de proveedor, ajustes y fecha de cierre.</p>
              <h4>¿De dónde salen los datos?</h4>
              <p>Yahoo Finance, con cinco años de históricos. ${esc(data.priceConvention)} Se cruzan sólo las fechas con datos en ambas series, sin inventar cierres. En semanal se usa la última sesión real de una semana completada, incluidos los festivos.</p>
              <p>Las EMA sólo usan la fecha calculada y las anteriores. Se descartan cinco ventanas N de calentamiento. Las pruebas comprueban, entre otras cosas, que comparar un activo consigo mismo da (100,100), que cambiar la escala del precio no altera el resultado y que añadir datos futuros no modifica los valores anteriores sobre una misma serie de precios.</p>
            </section>
            <p>Los enlaces conservan la configuración y abren los datos más recientes; la fecha explorada no se guarda. Un cruce por 100 no constituye una señal de compra o venta.</p>
            <p>Fuente: <a href="${esc(data.sourceUrl)}" target="_blank" rel="noopener noreferrer">Yahoo Finance</a> mediante <a href="https://github.com/ranaroussi/yfinance" target="_blank" rel="noopener noreferrer">yfinance</a>. No constituye recomendación de inversión.</p>
          </div>
        </details>`;

  root.innerHTML = `
    <header class="page-header">
      <div class="identity"><div class="brand-mark">${icon('orbit')}</div><div><h1>Órbita<span> / rotación relativa</span></h1><p>Una perspectiva distinta del mercado.</p></div></div>
      <div class="header-actions"><span class="status-pill ${stale || refreshFailed ? 'warning' : ''}"><i></i>${stale ? 'Revisar antigüedad' : refreshFailed ? 'Última copia válida' : 'Cierres disponibles'}</span><button id="share" class="button primary">${icon('share')}<span>Copiar enlace</span></button></div>
    </header>
    ${methodologyMarkup}
    <div id="notice" class="notice" role="status" hidden></div>
    ${stale || refreshFailed || futureClock ? `<div class="notice">${stale ? 'Los históricos tienen más de cinco días naturales. ' : ''}${refreshFailed ? 'La última actualización falló; se conserva el conjunto válido anterior. ' : ''}${futureClock ? 'La fecha de tu dispositivo es anterior a la del dataset. ' : ''}Consulta las fechas antes de interpretar el gráfico.</div>` : ''}
    <main class="workspace">
      <aside class="sidebar">
        <details id="settings" open><summary>Configurar vista <span>＋</span></summary>
          <div class="settings-content">
            <div class="section-label">UNIVERSO</div><div id="groups" class="segmented"></div>
            <label class="field-label" for="benchmark">Comparar frente a</label><select id="benchmark"></select><p class="field-note" id="benchmark-type"></p>
            <div class="section-label spaced">PERIODICIDAD</div><div class="segmented" id="timeframes"><button data-tf="daily">Diario</button><button data-tf="weekly">Semanal</button></div>
            <div class="selection-title"><span class="section-label">ACTIVOS</span><span class="count" id="selection-count"></span></div>
            <label class="search">${icon('search')}<input id="search" type="search" placeholder="Buscar nombre o ticker" aria-label="Buscar activos"></label>
            <div class="selection-actions"><button id="all">Todos</button><span>·</span><button id="none">Ninguno</button><button id="preset" class="push-right">Restablecer</button></div>
            <div id="asset-list" class="asset-list"></div>
            <div class="sidebar-foot">Sólo instrumentos del catálogo validado.<br>Todos en USD · sesiones cerradas.</div>
          </div>
        </details>
        <div class="reading-card"><span class="section-label">CÓMO LEERLO</span><p>La posición muestra la fuerza.<br>La cola cuenta el recorrido.</p><span>Arriba: gana momentum.<br>Derecha: fuerza relativa sobre 100.</span></div>
      </aside>
      <section class="main-column" aria-label="Explorador de rotación relativa">
        <section class="chart-card">
          <div class="card-heading"><div><div class="eyebrow" id="view-eyebrow"></div><h2>El mercado, en movimiento</h2></div><div class="date-block"><span>FECHA EXPLORADA</span><strong id="explored-date"></strong></div></div>
          <div class="benchmark-heading"><span id="benchmark-heading"></span><span id="benchmark-price"></span></div>
          <div id="benchmark-chart" class="benchmark-chart" role="img" aria-label="Histórico del benchmark con ventana temporal arrastrable"></div>
          <div class="playback">
            <div class="transport"><button id="back" class="icon-button" title="Periodo anterior" aria-label="Periodo anterior">${icon('left')}</button><button id="play" class="play-button" aria-label="Reproducir histórico">${icon('play')}<span>Reproducir</span></button><button id="forward" class="icon-button" title="Periodo siguiente" aria-label="Periodo siguiente">${icon('right')}</button><button id="latest" class="text-button">Última sesión</button></div>
            <label class="tail-control" for="tail-range">Cola <input id="tail-range" type="range" min="1" max="30"><input id="tail-number" type="number" min="1" max="30" aria-label="Longitud de cola"><span id="tail-unit"></span></label>
          </div>
          <label class="timeline-accessible">Fecha del recorrido<input id="date-range" type="range" min="0" aria-label="Fecha del recorrido"></label>
          <div class="chart-toolbar"><div class="scale-buttons" role="group" aria-label="Escala del gráfico"><button data-scale="fit" title="Ajustar las trayectorias actuales">Ajustar</button><button data-scale="max" title="Encuadrar todo el histórico">Histórico</button><button data-scale="center" title="Centrar en 100,100">Centrar</button></div><label class="checkbox small"><input id="scale-lock" type="checkbox" checked> Fijar ajuste</label><label class="checkbox small push-right"><input id="arrows" type="checkbox"> Flechas</label><button id="zoom-reset" class="icon-button" title="Restablecer zoom" aria-label="Restablecer zoom">${icon('reset')}</button></div>
          <div class="rotation-wrap"><div id="rotation-chart" class="rotation-chart" role="img" aria-label="Rotación de activos en cuatro cuadrantes; valores disponibles también en la tabla"></div><div id="empty-chart" class="empty-chart" hidden>Selecciona algún activo para explorar su rotación.</div></div>
          <div class="chart-caption"><span>Arrastra para desplazar · rueda o pellizca para acercar</span><span id="period-caption"></span></div>
        </section>
        <section class="table-card"><div class="table-heading"><div><h2>Una mirada a los activos</h2><p>Selecciona una fila para seguir su trayectoria.</p></div><button id="table-toggle" class="text-button" aria-expanded="true">Ocultar tabla</button></div><div id="table-content" class="table-scroll"><table><thead><tr>
          <th scope="col"><span class="sr-only">Visible</span></th><th scope="col"><button data-sort="name">Activo ↕</button></th><th scope="col"><button data-sort="quadrant">Cuadrante ↕</button></th><th scope="col"><button data-sort="x">Fuerza ↕</button></th><th scope="col"><button data-sort="y">Momentum ↕</button></th><th scope="col">Δ fuerza / momentum¹</th><th scope="col">Cambio de cuadrante¹</th><th scope="col">Cierre comparable</th><th scope="col">Fecha</th>
        </tr></thead><tbody id="table-body"></tbody></table></div><p class="table-note">¹ Frente al periodo anterior. El cierre de un ETF está ajustado por dividendos y splits.</p></section>
        <section class="quadrant-guide" aria-label="Interpretación de cuadrantes">${(['improving', 'leading', 'lagging', 'weakening'] as const).map(q => `<div><span class="quadrant-dot" style="background:${quadrants[q].color}"></span><strong>${quadrants[q].name}</strong><p>${quadrants[q].hint}</p></div>`).join('')}</section>

      </section>
    </main>
    <footer class="page-footer"><span>${icon('orbit')} Órbita <span class="muted">· una vista relativa</span></span><div><span>Última sesión de mercado: <b>${formatDate(data.latestSession)}</b></span><span>Actualización: <b>${new Date(data.generatedAt).toLocaleString('es-ES', { timeZone: 'Europe/Madrid', dateStyle: 'short', timeStyle: 'short' })} · Madrid</b></span><span>Yahoo Finance · USD</span></div></footer>
    <div id="toast" class="toast" role="status" hidden></div>`;

  const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
  const input = (id: string) => el<HTMLInputElement>(id);
  const rotation = initChart(el('rotation-chart'));
  const benchmarkChart = initChart(el('benchmark-chart'));
  const toast = (message: string) => { el('toast').textContent = message; el('toast').hidden = false; setTimeout(() => el('toast').hidden = true, 3000); };
  let emptyTimer: ReturnType<typeof setTimeout> | undefined;
  const writeUrl = () => history.replaceState(null, '', `${location.pathname}?${serialize(state)}${location.hash}`);

  function stop() {
    clearInterval(timer); timer = undefined; playing = false;
    el('play').innerHTML = `${icon('play')}<span>Reproducir</span>`;
    el('play').setAttribute('aria-label', 'Reproducir histórico');
  }
  function setEnd(index: number) {
    const max = view().benchmark.length - 1;
    end = Math.max(0, Math.min(max, index));
    render();
    if (end === max && playing) stop();
  }
  function rebuildControls() {
    el('groups').innerHTML = Object.entries(data.groups).map(([key, group]) => `<button data-group="${key}" class="${key === state.group ? 'active' : ''}" aria-pressed="${key === state.group}">${esc(group!.name)}</button>`).join('');
    el<HTMLSelectElement>('benchmark').innerHTML = data.groups[state.group]!.benchmarks.map(id => `<option value="${id}">${esc(instrumentLabel(id))} (${esc(instrument(id).ticker)})</option>`).join('');
    el<HTMLSelectElement>('benchmark').value = state.benchmark;
    el('benchmark-type').textContent = instrument(state.benchmark).type === 'index' ? 'Índice real · cierre de precio' : 'ETF proxy · cierre ajustado';
    document.querySelectorAll<HTMLElement>('[data-tf]').forEach(b => { b.classList.toggle('active', b.dataset.tf === state.tf); b.setAttribute('aria-pressed', String(b.dataset.tf === state.tf)); });
    input('tail-range').value = input('tail-number').value = String(state.tail);
    input('arrows').checked = state.arrows;
    el('tail-unit').textContent = state.tf === 'weekly' ? 'sem.' : 'ses.';
    buildAssets();
  }
  function buildAssets() {
    const search = input('search').value.trim().toLocaleLowerCase('es');
    const items = data.catalog.filter(i => i.group === state.group && i.id !== state.benchmark && view().assets[i.id]);
    const filtered = items.filter(i => `${i.id} ${i.name} ${i.ticker}`.toLocaleLowerCase('es').includes(search));
    el('asset-list').innerHTML = filtered.map(i => `<label class="asset-option ${state.selected.includes(i.id) ? 'selected' : ''}"><input type="checkbox" data-asset="${i.id}" ${state.selected.includes(i.id) ? 'checked' : ''}><span class="asset-color" style="background:${color(i.id)}"></span><span><strong>${esc(i.id)}</strong><small>${esc(i.name)}</small></span><span class="type-tag">${i.type === 'index' ? 'Índice' : i.proxyOf ? 'Proxy' : 'ETF'}</span></label>`).join('') || '<p class="field-note">No hay coincidencias.</p>';
    el('selection-count').textContent = `${state.selected.filter(i => i !== state.benchmark).length} / ${items.length}`;
  }
  function assetsAtDate(): PlotAsset[] {
    return state.selected.filter(id => id !== state.benchmark && !state.hidden.includes(id) && view().assets[id]).map(id => ({
      id, name: instrument(id).name, color: color(id), points: trail(view().assets[id], currentDate(), state.tail), faded: highlighted !== null && highlighted !== id,
    }));
  }
  function computeBounds(assets: PlotAsset[]) {
    const points = scaleMode === 'max' ? assets.flatMap(a => view().assets[a.id]) : assets.flatMap(a => a.points);
    const b = scaleBounds(points, scaleMode === 'center');
    const ratio = Math.max(1, rotation.getWidth() - 92) / Math.max(1, rotation.getHeight() - 63);
    const cx = (b[0] + b[1]) / 2, cy = (b[2] + b[3]) / 2;
    const dx = Math.max(b[1] - b[0], (b[3] - b[2]) * ratio) / 2;
    const dy = Math.max(b[3] - b[2], (b[1] - b[0]) / ratio) / 2;
    return [cx - dx, cx + dx, cy - dy, cy + dy];
  }
  function render(reset = false) {
    const series = view().benchmark, date = currentDate(), assets = assetsAtDate();
    if (!bounds || lock || reset) bounds = computeBounds(assets);
    rotation.setOption(rotationOptions(assets, bounds, state.arrows, instrument(state.benchmark).ticker, reset || lock), { replaceMerge: ['series'] });
    benchmarkChart.setOption(benchmarkOptions(series, end, state.tail, instrument(state.benchmark).ticker), true);
    el('explored-date').textContent = formatDate(date);
    el('view-eyebrow').textContent = `${data.groups[state.group]!.name} / ${state.tf === 'weekly' ? 'SEMANAL' : 'DIARIO'} / FRENTE A ${instrument(state.benchmark).ticker}`;
    el('benchmark-heading').textContent = `${instrument(state.benchmark).name} · ${instrument(state.benchmark).ticker}${instrument(state.benchmark).proxyOf ? ' · ETF proxy' : ''}`;
    el('benchmark-price').textContent = `${fmt(series[end][1])} ${instrument(state.benchmark).type === 'index' ? 'ptos.' : 'USD ajustados'}`;
    input('date-range').max = String(series.length - 1); input('date-range').value = String(end);
    el<HTMLButtonElement>('back').disabled = end === 0;
    el<HTMLButtonElement>('forward').disabled = end === series.length - 1;
    el('latest').classList.toggle('at-latest', end === series.length - 1);
    el('period-caption').textContent = `${state.tail} ${state.tf === 'weekly' ? 'semanas' : 'sesiones'} · centro 100 / 100`;
    el('empty-chart').hidden = assets.some(a => a.points.length > 0);
    renderTable();
    document.querySelectorAll<HTMLElement>('[data-scale]').forEach(b => { b.classList.toggle('active', b.dataset.scale === scaleMode); b.setAttribute('aria-pressed', String(b.dataset.scale === scaleMode)); });
    writeUrl();
  }
  function renderTable() {
    const rows = state.selected.filter(id => id !== state.benchmark && view().assets[id]).map(id => {
      const points = trail(view().assets[id], currentDate(), 1), p = points.at(-1), previous = points.at(-2);
      return { id, name: instrument(id).name, p, previous, x: p?.[1] ?? -Infinity, y: p?.[2] ?? -Infinity,
        quadrant: p ? quadrants[quadrant(p[1], p[2])].name : '' };
    });
    rows.sort((a, b) => {
      const av = a[sortKey as 'name' | 'quadrant' | 'x' | 'y'], bv = b[sortKey as 'name' | 'quadrant' | 'x' | 'y'];
      return (typeof av === 'number' ? av - (bv as number) : av.localeCompare(String(bv), 'es')) * (ascending ? 1 : -1);
    });
    const delta = (v: number) => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v))}`;
    el('table-body').innerHTML = rows.map(({ id, name, p, previous }) => {
      const q = p ? quadrant(p[1], p[2]) : 'neutral', before = previous ? quadrant(previous[1], previous[2]) : q;
      const old = p && p[0] !== currentDate();
      return `<tr data-row="${id}" class="${highlighted === id ? 'highlighted' : ''} ${state.hidden.includes(id) ? 'dimmed' : ''}"><td><input type="checkbox" data-visible="${id}" aria-label="Mostrar ${id}" ${state.hidden.includes(id) ? '' : 'checked'}></td><th scope="row"><button class="row-name" data-highlight="${id}" aria-pressed="${highlighted === id}"><span class="asset-color" style="background:${color(id)}"></span><span><strong>${esc(id)}</strong><small>${esc(name)}</small></span></button></th>${p ? `<td><span class="quadrant-badge" style="color:${quadrants[q].color};background:${quadrants[q].fill}">${quadrants[q].name}</span></td><td class="number">${fmt(p[1])}</td><td class="number">${fmt(p[2])}</td><td class="number movement">${previous ? `${delta(p[1] - previous[1])} / ${delta(p[2] - previous[2])}` : '—'}</td><td class="transition">${q !== before ? `${quadrants[before].name} → ${quadrants[q].name}` : 'Sin cambio'}</td><td class="number">${fmt(p[3])} <span class="muted">${instrument(id).type === 'index' ? 'ptos.' : 'USD'}</span></td><td class="row-date ${old ? 'warning-text' : ''}">${formatDate(p[0])}${old ? ' · anterior' : ''}</td>` : '<td colspan="7">Sin datos en esta fecha</td>'}</tr>`;
    }).join('') || '<tr><td colspan="9" class="empty-table">Selecciona activos del panel para compararlos.</td></tr>';
  }
  function configurationChanged(date?: string) {
    stop(); highlighted = null; bounds = undefined;
    end = date ? Math.max(0, indexAtOrBefore(view().benchmark, date)) : view().benchmark.length - 1;
    rebuildControls(); render(true);
  }

  el('groups').addEventListener('click', event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>('[data-group]'); if (!button) return;
    const tf = state.tf, tail = state.tail, arrows = state.arrows;
    state = { ...defaults(data, button.dataset.group as Group), tf, tail, arrows };
    input('search').value = ''; configurationChanged();
  });
  el('benchmark').addEventListener('change', () => {
    const date = end === view().benchmark.length - 1 ? undefined : currentDate();
    state.benchmark = el<HTMLSelectElement>('benchmark').value; configurationChanged(date);
  });
  el('timeframes').addEventListener('click', event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>('[data-tf]'); if (!button || state.tf === button.dataset.tf) return;
    const date = end === view().benchmark.length - 1 ? undefined : currentDate();
    state.tf = button.dataset.tf as Timeframe; configurationChanged(date);
  });
  input('search').addEventListener('input', buildAssets);
  el('asset-list').addEventListener('change', event => {
    const checkbox = event.target as HTMLInputElement, id = checkbox.dataset.asset; if (!id) return;
    if (checkbox.checked) state.selected.push(id); else { state.selected = state.selected.filter(x => x !== id); state.hidden = state.hidden.filter(x => x !== id); }
    if (highlighted === id) highlighted = null;
    buildAssets(); render(true);
  });
  el('all').addEventListener('click', () => { state.selected = data.catalog.filter(i => i.group === state.group && i.id !== state.benchmark && view().assets[i.id]).map(i => i.id); state.hidden = []; buildAssets(); render(true); });
  el('none').addEventListener('click', () => { state.selected = []; state.hidden = []; highlighted = null; buildAssets(); render(true); });
  el('preset').addEventListener('click', () => { state.selected = [...data.groups[state.group]!.defaults]; state.hidden = []; highlighted = null; buildAssets(); render(true); });
  const setTail = (value: string) => { const number = Number(value); if (!Number.isFinite(number)) return; state.tail = Math.max(1, Math.min(30, Math.round(number))); input('tail-range').value = input('tail-number').value = String(state.tail); render(true); };
  input('tail-range').addEventListener('input', () => setTail(input('tail-range').value));
  input('tail-number').addEventListener('input', () => { if (input('tail-number').value) setTail(input('tail-number').value); });
  input('tail-number').addEventListener('change', () => setTail(input('tail-number').value));
  input('arrows').addEventListener('change', () => { state.arrows = input('arrows').checked; render(); });
  input('scale-lock').addEventListener('change', () => { lock = input('scale-lock').checked; if (lock) render(true); });
  document.querySelectorAll<HTMLElement>('[data-scale]').forEach(button => button.addEventListener('click', () => { scaleMode = button.dataset.scale as typeof scaleMode; render(true); }));
  el('zoom-reset').addEventListener('click', () => render(true));
  el('back').addEventListener('click', () => { stop(); setEnd(end - 1); });
  el('forward').addEventListener('click', () => { stop(); setEnd(end + 1); });
  el('latest').addEventListener('click', () => { stop(); setEnd(view().benchmark.length - 1); });
  input('date-range').addEventListener('input', () => { stop(); setEnd(Number(input('date-range').value)); });
  el('play').addEventListener('click', () => {
    if (playing) { stop(); return; }
    if (end === view().benchmark.length - 1) setEnd(Math.max(state.tail, end - (state.tf === 'weekly' ? 52 : 126)));
    playing = true; el('play').innerHTML = `${icon('pause')}<span>Pausar</span>`; el('play').setAttribute('aria-label', 'Pausar histórico');
    timer = setInterval(() => setEnd(end + 1), 450);
  });
  document.addEventListener('keydown', event => {
    if ((event.target as HTMLElement).closest('input,select,textarea,button,summary') || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); stop(); setEnd(end + (event.key === 'ArrowLeft' ? -1 : 1)); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  benchmarkChart.on('datazoom', (event: any) => {
    const zoom = event.batch?.[0] ?? event; if (typeof zoom.end !== 'number') return;
    stop(); const target = Math.round(zoom.end / 100 * (view().benchmark.length - 1));
    if (target !== end) setEnd(target);
  });
  benchmarkChart.getZr().on('click', (event: any) => {
    if (event.offsetY > benchmarkChart.getHeight() - 40) return;
    const pixel = benchmarkChart.convertFromPixel({ xAxisIndex: 0 }, event.offsetX);
    if (Number.isFinite(pixel)) { stop(); setEnd(Math.round(Number(pixel))); }
  });
  rotation.on('click', (event: any) => { if (catalog.has(event.seriesName)) { highlighted = highlighted === event.seriesName ? null : event.seriesName; render(); } });
  el('table-body').addEventListener('click', event => {
    const target = event.target as HTMLElement;
    if (target.closest('input')) return;
    const row = target.closest<HTMLElement>('[data-row]'); if (!row) return;
    highlighted = highlighted === row.dataset.row ? null : row.dataset.row!; render();
  });
  el('table-body').addEventListener('change', event => {
    const checkbox = event.target as HTMLInputElement, id = checkbox.dataset.visible; if (!id) return;
    state.hidden = checkbox.checked ? state.hidden.filter(i => i !== id) : [...state.hidden, id];
    if (highlighted === id && !checkbox.checked) highlighted = null;
    render(true);
  });
  document.querySelectorAll<HTMLElement>('[data-sort]').forEach(button => button.addEventListener('click', () => {
    ascending = sortKey === button.dataset.sort ? !ascending : true; sortKey = button.dataset.sort!;
    document.querySelectorAll('[aria-sort]').forEach(node => node.removeAttribute('aria-sort'));
    button.closest('th')?.setAttribute('aria-sort', ascending ? 'ascending' : 'descending'); renderTable();
  }));
  el('table-toggle').addEventListener('click', () => {
    el('table-content').hidden = !el('table-content').hidden;
    el('table-toggle').textContent = el('table-content').hidden ? 'Mostrar tabla' : 'Ocultar tabla';
    el('table-toggle').setAttribute('aria-expanded', String(!el('table-content').hidden));
  });
  el('share').addEventListener('click', async () => {
    writeUrl();
    try {
      await navigator.clipboard.writeText(location.href); toast('Enlace copiado · abrirá los cierres más recientes');
    } catch {
      el('notice').hidden = false; el('notice').replaceChildren();
      const label = document.createElement('label'); label.textContent = 'Copia este enlace: ';
      const field = document.createElement('input'); field.type = 'text'; field.value = location.href; field.readOnly = true; field.setAttribute('aria-label', 'Enlace para copiar');
      label.append(field); el('notice').append(label); field.focus(); field.select();
    }
  });
  addEventListener('popstate', () => { state = parseState(location.search, data); configurationChanged(); });
  const observer = new ResizeObserver(() => { clearTimeout(emptyTimer); emptyTimer = setTimeout(() => { rotation.resize(); benchmarkChart.resize(); if (lock) render(true); }, 60); });
  observer.observe(el('rotation-chart')); observer.observe(el('benchmark-chart'));
  if (matchMedia('(max-width: 760px)').matches) el<HTMLDetailsElement>('settings').open = false;
  if (Object.keys(data.errors).length) { el('notice').textContent = `Instrumentos no disponibles: ${Object.keys(data.errors).join(', ')}. El resto del catálogo funciona.`; el('notice').hidden = false; }
  configurationChanged();
  if (location.hash === '#para-kiko') {
    el<HTMLDetailsElement>('methodology').open = true;
    requestAnimationFrame(() => el('para-kiko').scrollIntoView({ block: 'start' }));
  }
}

boot().catch(error => {
  root.innerHTML = `<main class="error-page"><div class="brand-mark">${icon('orbit')}</div><h1>No hemos podido abrir el mercado</h1><p>${esc(error instanceof Error ? error.message : 'Error de carga inesperado.')}</p><button class="button primary" id="retry">Volver a intentar</button></main>`;
  document.getElementById('retry')!.addEventListener('click', () => location.reload());
});
