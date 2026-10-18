import './strategies.css';
import { currentResultsMarkup, bindCurrentResults, researchControls } from './current-results';
import { initChart, rotationOptions, type Chart } from './charts';
import { indexAtOrBefore, scaleBounds, type Point } from './model';
import { entryNames, parseStrategy, strategySearch, validateCase, validateManifest, safeArtifact,
  type CaseData, type SignalEvent, type StrategyManifest, type StrategyState } from './strategies-model';

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const percent = (n: number | null | undefined) => n == null ? 'No disponible' : `${(n * 100).toLocaleString('es-ES', { maximumFractionDigits: 2 })} %`;
const decimal = (n: number | null | undefined) => n == null ? '—' : n.toLocaleString('es-ES', { maximumFractionDigits: 2 });

export async function mountStrategies(container: HTMLElement) {
  let state = parseStrategy(location.search);
  let manifest: StrategyManifest;
  let detail: CaseData | undefined;
  let selected: SignalEvent | undefined;
  let revealed = false, cursor = 0, requestId = 0;
  let priceChart: Chart | undefined, orbitChart: Chart | undefined;
  let resultCharts: Chart[] = [];
  let stockReport: any;
  let currentReport: any;
  const quantControls = researchControls();
  let executionDetails: Record<string, any> | undefined;
  let executionRule = 'time-13';
  const base = `${import.meta.env.BASE_URL}data/strategies/`;
  const cache = new Map<string, CaseData>();
  const fetchJson = async (path: string) => {
    const response = await fetch(base + safeArtifact(path), { cache: 'no-cache' });
    if (!response.ok) throw new Error('No se pudo cargar el informe. Reintenta en unos momentos.');
    return response.json();
  };
  const updateUrl = () => { if (!container.hidden) history.replaceState(null, '', `${location.pathname}?${strategySearch(state, location.search)}#estrategias`); };
  const status = () => manifest.currentCoverage ? `S&P 500 actual · ${manifest.currentCoverage.count} valores` : manifest.audit.status === 'eligible' ? 'Auditoría superada' : 'S&P 500 histórico · no evaluable';
  const dispose = () => { priceChart?.dispose(); orbitChart?.dispose(); resultCharts.forEach(c=>c.dispose()); resultCharts=[]; priceChart = orbitChart = undefined; };
  const observer = new ResizeObserver(() => { if (!container.hidden) { priceChart?.resize(); orbitChart?.resize(); resultCharts.forEach(c=>c.resize()); drawCase(); } });
  observer.observe(container);
  async function load() {
    container.innerHTML = '<p class="strategy-loading" role="status">Cargando estrategias y cobertura…</p>';
    try {
      manifest = validateManifest(await fetchJson('manifest.json'));
      if (manifest.currentStudyUrl && !new URLSearchParams(location.search).has('sv')) state = {...state, universe:'stocks',page:'results',tf:'weekly'};
      if(manifest.currentStudyUrl && manifest.currentRefreshStatusUrl) try {
        const refresh=await fetchJson(manifest.currentRefreshStatusUrl);manifest.currentRefreshFailed=refresh.ok===false;
      } catch { /* Older valid reports predate the separate refresh status. */ }
      try {
        const status = await fetchJson('refresh-status.json');
        if (status.ok === false) manifest = { ...manifest, researchRefreshFailed: true } as StrategyManifest;
      } catch { /* Optional refresh status; the manifest retains its own dates. */ }
      await render();
    } catch (error) {
      container.innerHTML = `<div class="strategy-warning"><h2>Estrategias no disponibles</h2><p>${esc((error as Error).message)}</p><button class="button" id="strategy-retry">Reintentar</button></div>`;
      container.querySelector('#strategy-retry')!.addEventListener('click', load);
    }
  }
  function toolbar() {
    const available = manifest.cases.filter(c => c.timeframe === state.tf && c.scope === (state.universe === 'indices' ? 'index-illustration' : 'stock-study'));
    const stocks = state.universe === 'stocks';
    return `<div class="strategy-controls">
      <label>Universo<select id="study-universe"><option value="indices" ${!stocks ? 'selected' : ''}>Casos reales · índices</option><option value="stocks" ${stocks ? 'selected' : ''}>${manifest.currentStudyUrl ? 'S&P 500 · componentes actuales' : 'S&P 500 histórico'}</option></select></label>
      <label>Periodicidad<select id="study-tf"><option value="weekly" ${state.tf === 'weekly' ? 'selected' : ''}>Semanal · principal</option><option value="daily" ${state.tf === 'daily' ? 'selected' : ''}>Diario · exploratorio</option></select></label>
      <label>Activo<select id="study-symbol" ${!available.length ? 'disabled' : ''}>${[...new Map(available.map(c => [c.securityId, c])).values()].map(c => `<option value="${esc(c.securityId)}" ${c.securityId === state.symbol ? 'selected' : ''}>${esc(c.securityId)} · ${esc(c.name)}</option>`).join('')}</select></label>
      <label>Entrada<select id="study-rule"><option value="all">Todas las entradas</option>${Object.entries(entryNames).map(([id, name]) => `<option value="${id}" ${state.rule === id ? 'selected' : ''}>${name}</option>`).join('')}</select></label>
      <label>Confirmación<select id="study-confirm"><option value="1" ${state.confirmation === 1 ? 'selected' : ''}>Primer periodo</option><option value="2" ${state.confirmation === 2 ? 'selected' : ''}>Dos periodos</option></select></label>
      <label>Referencia<select id="study-ref" ${!stocks ? 'disabled' : ''}><option value="market" ${state.reference === 'market' ? 'selected' : ''}>${stocks ? 'SPY · ETF proxy del S&P 500' : 'S&P 500 · índice ^GSPC'}</option><option value="sector" ${state.reference === 'sector' ? 'selected' : ''}>ETF del sector vigente</option></select></label>
      <label class="strategy-check"><input id="study-strong" type="checkbox" ${state.strong ? 'checked' : ''} ${!stocks ? 'disabled' : ''}> Sector en Líder</label>
      <label class="strategy-check"><input id="study-volume" type="checkbox" ${state.volume ? 'checked' : ''} ${!stocks ? 'disabled' : ''}> Volumen relativo ≥ 1,2</label>
    </div>`;
  }
  function coverageMarkup() {
    if (manifest.currentCoverage) return `<details class="strategy-coverage"><summary>Universo actual y límites del estudio</summary><p>Se incluyen los ${manifest.currentCoverage.count} valores de la composición actual del S&P 500, registrada el ${esc(manifest.currentCoverage.asOf)}. Se utiliza su historial disponible desde 2010. No se exige reconstruir empresas excluidas porque no forman parte de este estudio.</p><p>Esto introduce sesgo de supervivencia y aplica los sectores actuales al pasado. Permite comparar estas reglas sobre las acciones actuales; no reproduce la inversión histórica en los componentes que existían entonces. Los datos, métricas, periodos y asignación se detallan en Resultados.</p></details>`;
    const a = manifest.audit;
    return `<details class="strategy-coverage" ${state.universe === 'stocks' && a.status !== 'eligible' ? 'open' : ''}><summary>Cobertura y fuentes · ${esc(status())}</summary>
      <p>El estudio exige componentes y sectores conocidos en cada fecha, acciones excluidas, eventos corporativos y liquidaciones. Los huecos impiden declarar una ventaja.</p>
      ${a.coverage ? `<p>Intervalo solicitado: ${esc(a.coverage.start)} → ${esc(a.coverage.end)} · ${a.coverage.securities} valores · ${a.coverage.delisted} desaparecidos.</p>` : '<p>El catálogo disponible contiene índices y ETFs. Todavía no hay un universo histórico completo de acciones auditado.</p>'}
      ${manifest.candidateCoverage ? `<p><strong>Recopilación gratuita consultada:</strong> ${manifest.candidateCoverage.intervalRows} intervalos por ticker; ${manifest.candidateCoverage.tickersSince2010} tickers desde 2010 y ${manifest.candidateCoverage.closedIntervalsSince2010} intervalos terminados. Último cambio incluido: ${esc(manifest.candidateCoverage.latestChange)}. Son candidatos pendientes de contraste; una exclusión o cambio de ticker no equivale a una empresa desaparecida.</p>` : ''}
      ${manifest.priceProbes?.length ? `<p><strong>Prueba de descarga del 18/10/2026:</strong> ${manifest.priceProbes.map(p => `${esc(p.ticker)}: ${p.status === 'candidate-only' ? `${p.sessions} sesiones, ${esc(p.first)} → ${esc(p.last)}` : 'OHLCV no entregado en esta comprobación'}`).join('; ')}. Los datos descargados permanecen privados y pendientes de contraste.</p>` : ''}
      ${a.issues.length ? `<ul>${a.issues.slice(0, 20).map(i => `<li>${esc(i.detail)} ${esc(i.securityId ?? '')} ${esc(i.date ?? '')}</li>`).join('')}</ul>${a.issues.length > 20 ? `<p>${a.issues.length} incidencias en total.</p>` : ''}` : '<p>El conjunto importado supera las comprobaciones de cobertura.</p>'}
      <div class="strategy-sources">${manifest.sources.map(s => `<article><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a><p>${esc(s.limitation)}</p></article>`).join('')}</div>
    </details>`;
  }
  function visibleSignals(): SignalEvent[] {
    return (detail?.signals ?? []).filter(s => s.confirmation === state.confirmation && (state.rule === 'all' || s.rule === state.rule)
      && (state.universe === 'indices' || !state.strong || s.sector_strong === true)
      && (state.universe === 'indices' || !state.volume || (s.relative_volume != null && s.relative_volume >= 1.2)));
  }
  function signalsMarkup() {
    const rows = visibleSignals().slice().reverse();
    return `<section class="strategy-card"><div class="strategy-card-heading"><div><h3>Señales detectadas</h3><p>${rows.length} eventos · confirmación de ${state.confirmation} periodo${state.confirmation === 1 ? '' : 's'} · ${state.universe === 'indices' ? 'ejemplos de índices, fuera del estudio de acciones' : (manifest.currentStudyUrl ? 'componentes actuales · sector actual' : 'universo histórico auditado')}</p></div></div>
      <div class="strategy-table-scroll"><table><thead><tr><th>Detectada al cierre</th><th>Entrada</th><th>Referencia</th><th>Sector</th><th>Volumen relativo</th><th></th></tr></thead><tbody>${rows.slice(0, 150).map(s => `<tr><td>${esc(s.date)}${s.origin_date !== s.date ? `<small>Giro inicial ${esc(s.origin_date)}</small>` : ''}</td><td>${esc(entryNames[s.rule])}</td><td>${esc(s.reference)}</td><td>${esc(s.sector ?? 'No aplica')}</td><td>${decimal(s.relative_volume)}</td><td><button class="strategy-link" data-case="${s.id}">Ver caso →</button></td></tr>`).join('') || '<tr><td colspan="6">No hay señales con estos filtros.</td></tr>'}</tbody></table></div>
      ${rows.length > 150 ? '<p class="strategy-note">Se muestran los 150 eventos más recientes. Filtra por entrada o activo.</p>' : ''}</section>`;
  }
  function caseMarkup() {
    if (!detail || !selected) return '<div class="strategy-card"><p>Selecciona una señal para recorrer su órbita y su precio.</p></div>';
    return `<section class="strategy-card"><div class="strategy-card-heading"><div><p class="strategy-eyebrow">${esc(detail.securityId)} · ${esc(detail.reference)} · ${detail.timeframe === 'weekly' ? 'semanal' : 'diario'}</p><h3>${esc(entryNames[selected.rule])}</h3><p>Detectada: ${esc(selected.date)}${selected.confirmation === 2 ? ` · giro inicial: ${esc(selected.origin_date)}` : ''}</p></div><button class="button primary" id="study-reveal">${revealed ? 'Ocultar futuro' : 'Ver qué pasó después'}</button></div>
      <p class="strategy-case-status" id="study-case-status" role="status"></p>
      <div id="study-price" class="strategy-price" role="img" aria-label="Evolución del precio hasta la fecha del recorrido"></div>
      <div class="strategy-case-transport"><label for="study-cursor">Fecha del recorrido <strong id="study-date"></strong></label><input id="study-cursor" type="range" min="0" max="${revealed ? detail.points.length - 1 : indexAtOrBefore(detail.points, selected.date)}" value="${cursor}" aria-label="Recorrer caso histórico"></div>
      <div id="study-orbit" class="strategy-orbit" role="img" aria-label="Órbita sincronizada con el precio"></div>
      <div class="strategy-orbit-legend"><span>↖ Mejorando</span><span>↗ Líder</span><span>↙ Rezagado</span><span>↘ Debilitándose</span></div>
      <p id="study-coordinates" class="strategy-note"></p>
      <details class="strategy-zones"><summary>Percentiles y nueve zonas · exploratorio</summary><p id="study-percentiles"></p><div class="strategy-zone-grid" id="study-zones" role="img" aria-label="Nueve zonas de terciles de fuerza y momentum"></div><p>Columnas: terciles de fuerza relativa, de menor a mayor. Filas: terciles de momentum, de mayor a menor. Es una clasificación relativa al grupo de esa fecha; los cuatro cuadrantes originales se mantienen.</p></details>
      <p class="strategy-note">${esc(detail.limitations)}</p><p class="strategy-note">Método: ${esc(detail.method)}. ${detail.scope === 'index-illustration' ? 'Volumen de índices: no disponible.' : ''} El futuro se oculta al abrir o cambiar de caso.</p>
      ${detail.scope === 'stock-study' && manifest.stockStudyUrl ? `<label class="strategy-exit-label">Salida simulada<select id="study-exit"><option value="orbit">Líder → Debilitándose</option>${['pct-10','pct-15','pct-20','atr-2','atr-3','atr-4'].flatMap(r => [r, r+'+orbit']).map(r=>`<option value="${r}" ${r===executionRule?'selected':''}>${r.replace('pct-', 'Trailing % ').replace('atr-', 'ATR × ').replace('+orbit',' + órbita')}</option>`).join('')}<option value="time-13" ${executionRule==='time-13'?'selected':''}>13 semanas</option><option value="time-26" ${executionRule==='time-26'?'selected':''}>26 semanas</option></select></label>` : ''}
      <div id="study-execution" class="strategy-note"></div></section>`;
  }
  async function resultsMarkup() {
    if (manifest.currentStudyUrl) {
      currentReport ??= await fetchJson(manifest.currentStudyUrl);
      if (state.tf !== 'weekly') return `<section class="strategy-card"><h3>Estudio de carteras semanal</h3><p>Las comparaciones de capital, entrenamiento y prueba final de acciones se calculan con señales semanales. Selecciona «Semanal · principal». Los ejemplos de índices diarios siguen disponibles en su universo.</p></section>`;
      return currentResultsMarkup(currentReport,state,quantControls);
    }
    if (!manifest.stockStudyUrl) return `<section class="strategy-card"><p class="strategy-eyebrow">EVALUACIÓN DE ESTRATEGIAS</p><h3>${manifest.studyState === 'private-results' ? 'Resultados privados · publicación pendiente de derechos de uso' : 'Todavía no podemos medir la ventaja en el S&P 500 histórico'}</h3>
      <p>${manifest.studyState === 'private-results' ? 'El estudio se ha calculado localmente. Las fuentes del conjunto no autorizan la publicación de sus detalles.' : 'Faltan datos materiales del universo histórico. Las señales de los índices sirven para comprobar los giros; no estiman la eficacia de una estrategia sobre acciones.'}</p>
      <div class="strategy-metrics"><div><strong>4 entradas</strong><span>Dos giros y dos cruces</span></div><div><strong>15 salidas</strong><span>Órbita, trailing y plazos fijos</span></div><div><strong>13 semanas</strong><span>Horizonte principal de entradas</span></div><div><strong>Sin conclusión</strong><span>Hasta disponer de evidencia suficiente</span></div></div>
      <h4>Cómo se compararán</h4><p>Señal al cierre y compra en la siguiente apertura. Costes de 5, 10 y 25 puntos básicos por lado. El estudio separa la calidad de la entrada del efecto de la salida y compara ambos con SPY, el sector y sus demás acciones.</p>
      <p>La salida se elige con cinco años anteriores y se evalúa en el siguiente. Se requieren al menos cinco años evaluados y cien operaciones para una conclusión favorable. Los casos conocidos de 2025 no son una prueba independiente.</p></section>`;
    stockReport ??= await fetchJson(manifest.stockStudyUrl);
    if (stockReport.version !== 1 || stockReport.protocolHash !== manifest.protocolHash || !Array.isArray(stockReport.variants)) throw new Error('Resultados incompatibles con el protocolo');
    const rows = stockReport.variants.filter((r: any) => r.timeframe === state.tf && r.reference === state.reference && r.confirmation === state.confirmation
      && r.sectorFilter === state.strong && (r.volumeFilter != null) === state.volume && (state.rule === 'all' || r.rule === state.rule));
    const conclusion: Record<string, string> = { 'inconclusive': 'Inconcluso', 'no-detectable-edge': 'Sin ventaja detectable', 'historically-consistent': 'Ventaja histórica consistente' };
    return `<section class="strategy-card"><h3>Resultados fuera de muestra · retrospectivos</h3><p>Tipo libre de riesgo: 0 %. Coste principal: 10 pb por lado. Los percentiles y variantes diarias son exploratorios.</p><div class="strategy-table-scroll"><table><thead><tr><th>Entrada</th><th>Operaciones cerradas / total</th><th>Mediana neta</th><th>Positivas</th><th>Sharpe</th><th>Caída máxima</th><th>Conclusión</th></tr></thead><tbody>${rows.map((r: any) => `<tr><td>${esc(entryNames[r.rule])}</td><td>${r.summary.closed} / ${r.summary.total}<small>${r.summary.open} abiertas · ${r.summary.missing} sin datos</small></td><td>${percent(r.summary.median)}</td><td>${percent(r.summary.winRate)}</td><td>${decimal(r.walkForward.portfolio.sharpe)}</td><td>${percent(r.walkForward.portfolio.maxDrawdown)}</td><td>${esc(conclusion[r.conclusion])}</td></tr>`).join('')}</tbody></table></div>
      ${rows.map((r: any) => `<details data-result-detail="${esc(r.detailsUrl)}"><summary>${esc(entryNames[r.rule])} · horizontes, salidas y evaluación</summary><p>${r.completeTestYears} años completos evaluados · IC 95 % del exceso neto: ${r.exitEvidence.interval ? r.exitEvidence.interval.map(percent).join(' a ') : 'muestra insuficiente'} · p ajustada: ${decimal(r.adjustedPValue)}</p>
        <table><thead><tr><th>Horizonte</th><th>Cerradas / total</th><th>Media</th><th>Mediana</th></tr></thead><tbody>${Object.entries(r.horizons).map(([h, v]: [string, any]) => `<tr><td>${h} semanas</td><td>${v.closed} / ${v.total}</td><td>${percent(v.mean)}</td><td>${percent(v.median)}</td></tr>`).join('')}</tbody></table>
        <p>Distribución neta (P5, P25, P50, P75, P95): ${r.summary.quantiles ? r.summary.quantiles.map(percent).join(' · ') : 'Sin operaciones cerradas'}</p>
        <p>Exceso de la entrada a 13 semanas frente a SPY: ${percent(r.entryEvidence.mean)} · IC 95 %: ${r.entryEvidence.interval ? r.entryEvidence.interval.map(percent).join(' a ') : 'muestra insuficiente'}.</p>
        <table><thead><tr><th>Coste por lado</th><th>Retorno de cartera de referencia</th><th>Caída máxima</th></tr></thead><tbody>${Object.entries(r.costs).map(([c, v]: [string, any]) => `<tr><td>${c} pb</td><td>${percent(v.totalReturn)}</td><td>${percent(v.maxDrawdown)}</td></tr>`).join('')}</tbody></table>
        <table><thead><tr><th>Evaluación</th><th>Entrenamiento hasta</th><th>Salida elegida</th></tr></thead><tbody>${r.walkForward.folds.map((f: any) => `<tr><td>${esc(f.testStart)} → ${esc(f.testEnd)}</td><td>${esc(f.trainingEnd)}</td><td>${esc(f.chosenExit ?? 'Evidencia insuficiente')}</td></tr>`).join('')}</tbody></table>
        <div class="strategy-result-curve" role="img" aria-label="Cartera de referencia y SPY fuera de muestra"></div><p class="strategy-note">Cartera equiponderada y SPY comprado en la primera apertura, ambos valorados al cierre; efectivo al 0 %. Las operaciones, costes y periodos completos están registrados.</p></details>`).join('')}</section>`;
  }
  function protocolMarkup() {
    if(manifest.currentStudyUrl) return `<details class="strategy-coverage"><summary>Las cuatro entradas y las reglas de cartera</summary><div class="strategy-rules">${Object.entries(entryNames).map(([id,name])=>`<article><strong>${esc(name)}</strong><p>${({'turn-up':'El momentum Y cambia de pendiente no positiva a positiva, permaneciendo en Rezagado.','turn-right':'La fuerza X cambia de pendiente no positiva a positiva, permaneciendo en Rezagado.','lagging-improving':'Y cruza 100 hacia arriba con X por debajo de 100.','improving-leading':'X cruza 100 hacia arriba con Y por encima de 100.'} as Record<string,string>)[id]}</p></article>`).join('')}</div><p>Semanal: X = 100 × SMA(RS,10) / SMA(RS,30); Y = 100 × X / SMA(X,9). Fórmula propia experimental; no equivale a JdK. Sólo semanas completadas y ejecución a la siguiente apertura.</p><p>«Entradas y salidas» compara las reglas con asignación idéntica. «Carteras» añade selección, pesos, límites y efectivo. El protocolo del universo actual, los cortes temporales y las huellas de datos y código aparecen en los resultados. Los ejemplos diarios de índices se mantienen como exploración separada.</p></details>`;
    return `<details class="strategy-coverage"><summary>Reglas, protocolo y seguimiento prospectivo</summary><div class="strategy-rules">${Object.entries(entryNames).map(([id, name]) => `<article><strong>${esc(name)}</strong><p>${({ 'turn-up': 'Y empieza a subir después de un cambio no positivo, mientras el activo permanece en Rezagado.', 'turn-right': 'X empieza a subir después de un cambio no positivo, mientras el activo permanece en Rezagado.', 'lagging-improving': 'Y cruza por encima de 100, con X por debajo de 100.', 'improving-leading': 'X cruza por encima de 100, con Y por encima de 100.' } as Record<string, string>)[id]}</p></article>`).join('')}</div>
      <p>Semanal: X = 100 × SMA(RS,10) / SMA(RS,30); Y = 100 × X / SMA(X,9). Extensión experimental a acciones y sectores. Diario: EMA 50/20, resultados exploratorios separados.</p>
      <p>Salidas: Líder → Debilitándose; trailing del 10/15/20 %; ATR de 22 sesiones × 2/3/4; cada trailing combinado con la órbita; plazos de 13 y 26 semanas. Máximo: 52 semanas. Trailing actualizado al cierre, ejecución en la siguiente apertura.</p>
      <p>Protocolo congelado: ${esc(manifest.protocol.frozenOn)} · ${manifest.prospective.count} señales de acciones registradas prospectivamente. Registrar una señal histórica hoy no la convierte en evidencia prospectiva.</p>
      <p>Incertidumbre: remuestreo por bloques de calendario de 52 semanas y corrección de Holm. Todas las variantes se conservan; una selección sin evidencia estable queda inconclusa.</p>
      <p class="strategy-hash">Protocolo ${esc(manifest.protocolHash)}<br>Dataset ${esc(manifest.snapshotHash)}<br>Informe ${esc(manifest.runId)}</p>
    </details>`;
  }
  async function render() {
    const token = ++requestId;
    const files = manifest.cases.filter(c => c.timeframe === state.tf && c.scope === (state.universe === 'indices' ? 'index-illustration' : 'stock-study')
      && (!('referenceType' in c) || (c as any).referenceType === state.reference));
    const file = files.find(c => c.securityId === state.symbol) ?? files[0];
    if (file) {
      const loaded = cache.get(file.url) ?? validateCase(await fetchJson(file.url));
      if (token !== requestId) return;
      cache.set(file.url, loaded); detail = loaded; state.symbol = file.securityId;
    } else detail = undefined;
    const signals = visibleSignals();
    selected = signals.find(s => s.id === state.caseId) ?? signals.find(s => s.date === '2025-06-06' && s.rule === 'lagging-improving') ?? signals.at(-1);
    if (selected) state.caseId = selected.id; else state.caseId = '';
    revealed = false;
    cursor = detail && selected ? indexAtOrBefore(detail.points, selected.date) : 0;
    const content = state.page === 'results' ? await resultsMarkup() : state.page === 'case' ? caseMarkup() : signalsMarkup();
    if (token !== requestId) return;
    dispose();
    executionDetails = undefined;
    container.innerHTML = `<div class="strategy-intro"><p class="strategy-eyebrow">LABORATORIO DE ÓRBITA</p><h2>¿Qué aportan estos giros?</h2><p>Encuentra la entrada, recorre lo que ocurrió después y comprueba la evidencia.</p></div>
      <div class="strategy-warning" role="status"><strong>${esc(status())}</strong><p>${manifest.currentCoverage ? `${manifest.currentRefreshFailed?"La actualización falló; se conserva el último estudio válido con sus fechas originales. ":""}Resultados sobre los componentes actuales, con sesgo de supervivencia declarado. Acciones hasta ${esc(manifest.currentCoverage.latestSession)}. Compara entrenamiento, validación y prueba posterior.` : (manifest as any).researchRefreshFailed ? 'La actualización de investigación no superó la auditoría. Se conserva el último estudio válido con sus fechas originales.' : manifest.audit.status === 'eligible' ? 'El universo importado supera la auditoría. Consulta los resultados y su incertidumbre.' : 'El estudio de acciones espera un histórico completo. Puedes explorar ya los giros reales de los índices.'}</p></div>
      ${toolbar()}<nav class="strategy-tabs" aria-label="Vistas de estrategias">${[['signals', 'Señales'], ['case', 'Caso individual'], ['results', 'Resultados']].map(([id, name]) => `<button data-study-page="${id}" aria-pressed="${state.page === id}">${name}</button>`).join('')}<button id="study-share" class="push-right">Copiar este estudio ↗</button></nav>
      <div id="study-share-status" role="status"></div>${!detail && state.page !== 'results' ? '<section class="strategy-card"><h3>Universo todavía no evaluable</h3><p>Consulta «Cobertura y fuentes» para ver los datos pendientes. Los casos de índices están disponibles en el selector de universo.</p></section>' : content}
      ${coverageMarkup()}${protocolMarkup()}<p class="strategy-note">Última sesión: ${esc(manifest.latestSession)} · Informe: ${esc(manifest.generatedAt.slice(0, 10))}</p>`;
    const bind = (id: string, change: (element: HTMLInputElement) => void) => container.querySelector<HTMLInputElement>('#' + id)?.addEventListener('change', async event => {
      change(event.target as HTMLInputElement); state.caseId = ''; updateUrl(); await render().catch(showError);
    });
    bind('study-universe', e => { state.universe = e.value as StrategyState['universe']; state.reference = 'market'; state.strong = state.volume = false; });
    bind('study-tf', e => { state.tf = e.value as StrategyState['tf']; });
    bind('study-symbol', e => { state.symbol = e.value; });
    bind('study-rule', e => { state.rule = e.value; });
    bind('study-confirm', e => { state.confirmation = Number(e.value) as 1 | 2; });
    bind('study-ref', e => { state.reference = e.value as StrategyState['reference']; });
    bind('study-strong', e => { state.strong = e.checked; });
    bind('study-volume', e => { state.volume = e.checked; });
    container.querySelectorAll<HTMLButtonElement>('[data-study-page]').forEach(b => b.addEventListener('click', async () => { state.page = b.dataset.studyPage as StrategyState['page']; updateUrl(); await render().catch(showError); }));
    container.querySelectorAll<HTMLButtonElement>('[data-case]').forEach(b => b.addEventListener('click', async () => { state.caseId = b.dataset.case!; state.page = 'case'; updateUrl(); await render().catch(showError); }));
    container.querySelector('#study-share')?.addEventListener('click', share);
    if (state.page === 'results' && currentReport && state.tf === 'weekly') {
      container.querySelector<HTMLSelectElement>('#study-symbol')!.disabled=true;
      if(quantControls.mode==='allocation') for(const id of ['study-rule','study-confirm','study-ref','study-strong','study-volume']) {
        const input=container.querySelector<HTMLInputElement>('#'+id); if(input) input.closest('label')!.hidden=true;
      }
      void bindCurrentResults(container,currentReport,quantControls,fetchJson,()=>render().catch(showError),resultCharts,()=>token===requestId&&!container.hidden).catch(error=>{
        if(token===requestId) {const el=container.querySelector('#quant-curve');if(el)el.textContent=(error as Error).message;}
      });
    }
    container.querySelectorAll<HTMLDetailsElement>('[data-result-detail]').forEach(element => {
      let loaded = false;
      element.addEventListener('toggle', async () => {
        if (!element.open || loaded || !manifest.stockStudyUrl) return;
        loaded = true;
        try {
          const prefix = manifest.stockStudyUrl.slice(0, manifest.stockStudyUrl.lastIndexOf('/') + 1);
          const value = await fetchJson(prefix + safeArtifact(element.dataset.resultDetail!));
          if (token !== requestId) return;
          const series = value.variant?.walkForward?.portfolio?.equity;
          if (value.version !== 1 || !Array.isArray(series)) throw new Error('Curva de evaluación incompatible');
          const chart = initChart(element.querySelector<HTMLElement>('.strategy-result-curve')!);
          resultCharts.push(chart);
          chart.setOption({animation:false,legend:{data:['Cartera de referencia','SPY']},tooltip:{trigger:'axis',confine:true},
            grid:{left:50,right:20,top:45,bottom:35},xAxis:{type:'category',data:series.map((p:any)=>p[0])},yAxis:{type:'value',scale:true},
            series:[{name:'Cartera de referencia',type:'line',data:series.map((p:any)=>p[1]),showSymbol:false},
              {name:'SPY',type:'line',data:value.benchmarkEquity.map((p:any)=>p[1]),showSymbol:false}]});
        } catch(error) { element.querySelector('.strategy-result-curve')!.textContent = (error as Error).message; loaded=false; }
      });
    });
    if (state.page === 'case' && detail && selected) {
      initCase();
      if (detail.scope === 'stock-study' && manifest.stockStudyUrl) {
        const prefix = manifest.stockStudyUrl.slice(0, manifest.stockStudyUrl.lastIndexOf('/') + 1);
        void fetchJson(prefix + selected.id + '.json').then(value => {
          if (token !== requestId) return;
          if (value.version !== 1 || !value.trades) throw new Error('Detalle de operaciones incompatible');
          executionDetails = value.trades; drawCase();
        }).catch(error => { if (token === requestId) container.querySelector('#study-execution')!.textContent = (error as Error).message; });
      }
      container.querySelector('#study-exit')?.addEventListener('change', e => { executionRule = (e.target as HTMLSelectElement).value; drawCase(); });
      container.querySelector('#study-reveal')?.addEventListener('click', () => {
        revealed = !revealed;
        const at = indexAtOrBefore(detail!.points, selected!.date);
        cursor = revealed ? Math.min(detail!.points.length - 1, at + (state.tf === 'weekly' ? 13 : 65)) : at;
        const slider = container.querySelector<HTMLInputElement>('#study-cursor')!;
        slider.max = String(revealed ? detail!.points.length - 1 : at); slider.value = String(cursor);
        container.querySelector('#study-reveal')!.textContent = revealed ? 'Ocultar futuro' : 'Ver qué pasó después';
        drawCase();
      });
      container.querySelector('#study-cursor')?.addEventListener('input', e => { cursor = Number((e.target as HTMLInputElement).value); drawCase(); });
    }
    updateUrl();
  }
  function initCase() {
    priceChart = initChart(container.querySelector<HTMLElement>('#study-price')!);
    orbitChart = initChart(container.querySelector<HTMLElement>('#study-orbit')!);
    drawCase();
  }
  function drawCase() {
    if (!detail || !selected || !priceChart || !orbitChart) return;
    const last = detail.points[cursor];
    const points = detail.points.slice(Math.max(0, cursor - 17), cursor + 1);
    const start = Math.max(0, indexAtOrBefore(detail.points, selected.date) - (state.tf === 'weekly' ? 52 : 252));
    const firstDate = detail.points[start][0];
    const prices = detail.dailyPrices ? detail.dailyPrices.filter(p => firstDate <= p[0] && p[0] <= last[0]) : detail.points.slice(start, cursor + 1).map(p => [p[0], p[3]] as [string, number]);
    const selectedPoint = detail.points.find(p => p[0] === selected!.date)!;
    const future = last[0] > selected.date;
    container.querySelector('#study-date')!.textContent = last[0];
    container.querySelector('#study-case-status')!.textContent = future
      ? `Evolución del cierre desde la señal: ${percent(last[3] / selectedPoint[3] - 1)} · descriptiva, antes de costes.`
      : `Futuro ${revealed ? 'habilitado' : 'oculto'} · información visible hasta ${last[0]}.`;
    const execution = executionDetails?.[executionRule];
    const marks: any[] = selected.date <= last[0] ? [{ xAxis: selected.date, label: { formatter: 'Señal', position: 'insideEndTop' }, lineStyle: { color: '#456bc7' } }] : [];
    if (revealed && execution?.entryDate && execution.entryDate <= last[0]) marks.push({xAxis:execution.entryDate,label:{formatter:'Entrada'},lineStyle:{color:'#39765e'}});
    if (revealed && execution?.exitDate && execution.exitDate <= last[0]) marks.push({xAxis:execution.exitDate,label:{formatter:'Salida'},lineStyle:{color:'#ac605f'}});
    priceChart.setOption({ animation: false, grid: { left: 55, right: 22, top: 25, bottom: 35 },
      tooltip: { trigger: 'axis', confine: true }, xAxis: { type: 'category', data: prices.map(p => p[0]), axisLabel: { color: '#64735f', fontSize: 10 } },
      yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: '#e7ecdf' } } },
      series: [{ name: 'Cierre', type: 'line', data: prices.map(p => p[1]), showSymbol: false, lineStyle: { color: '#356c89', width: 2 },
        markLine: { symbol: 'none', data: marks } }] }, true);
    const bounds = scaleBounds(points), width = Math.max(80, orbitChart.getWidth() - 92), height = Math.max(80, orbitChart.getHeight() - 63);
    const unit = Math.max((bounds[1]-bounds[0])/width, (bounds[3]-bounds[2])/height);
    const mx = (bounds[0]+bounds[1])/2, my = (bounds[2]+bounds[3])/2;
    const options = rotationOptions([{ id: detail.securityId, name: detail.name, color: '#b65070', points, faded: false }],
      [mx-unit*width/2,mx+unit*width/2,my-unit*height/2,my+unit*height/2], true, detail.reference, true);
    if (orbitChart.getWidth() < 500) ((options.series as any[])[0].markArea.label).show = false;
    orbitChart.setOption(options, true);
    container.querySelector('#study-coordinates')!.textContent = `Fuerza relativa X: ${decimal(last[1])} · Momentum Y: ${decimal(last[2])} · ${last[0]}`;
    const executionElement = container.querySelector('#study-execution')!;
    executionElement.textContent = !execution ? '' : !revealed ? 'Las ejecuciones y resultados se muestran al revelar el recorrido posterior.'
      : execution.entryDate && execution.entryDate <= last[0]
      ? `Entrada simulada: ${execution.entryDate} · apertura ajustada ${decimal(execution.entryPrice)}. ${execution.exitDate && execution.exitDate <= last[0]
        ? `Salida: ${execution.exitDate} · neto ${percent(execution.netReturn)} · mayor avance ${percent(execution.mfe)} · mayor retroceso ${percent(execution.mae)} · ${execution.durationDays} días. Exceso frente a SPY ${percent(execution.excessMarket)}, sector ${percent(execution.excessSector)}, otras acciones elegibles ${percent(execution.excessPeers)} (${execution.peerCount ?? 0} acciones).`
        : 'Operación sin salida visible en esta fecha.'}`
      : 'Todavía no hay ejecución visible en esta fecha.';
    const ranked = detail.percentiles?.find(r => r.date === last[0]);
    const signalRank = detail.signals.find(s => s.date === last[0]);
    const x = ranked?.xPercentile ?? signalRank?.x_percentile, y = ranked?.yPercentile ?? signalRank?.y_percentile;
    const zone = ranked?.zone ?? signalRank?.zone;
    container.querySelector('#study-percentiles')!.textContent = x != null && y != null
      ? `Fuerza: percentil ${decimal(x)} · momentum: percentil ${decimal(y)} · ${ranked?.count ?? signalRank?.percentile_count} activos elegibles con la misma referencia, en ${last[0]}.`
      : 'Percentiles no disponibles para esta observación.';
    container.querySelector('#study-zones')!.innerHTML = Array.from({length: 9}, (_, n) => {
      const xx = n % 3, yy = 2 - Math.floor(n / 3), current = zone?.[0] === xx && zone?.[1] === yy;
      return `<div class="${current ? 'current' : ''}">${current ? esc(detail!.securityId) : '·'}</div>`;
    }).join('');
  }
  async function share() {
    updateUrl();
    const url = location.href;
    const target = container.querySelector<HTMLElement>('#study-share-status');
    if (!target) return;
    try { await navigator.clipboard.writeText(url); target.textContent = 'Enlace copiado · el caso se abrirá con el futuro oculto.'; }
    catch {
      target.replaceChildren(); const label = document.createElement('label'); label.textContent = 'Copia este enlace: ';
      const input = document.createElement('input'); input.readOnly = true; input.value = url; input.setAttribute('aria-label', 'Enlace del estudio');
      label.append(input); target.append(label); input.focus(); input.select();
    }
  }
  addEventListener('popstate', () => { state = parseStrategy(location.search); if (location.hash === '#estrategias') void render().catch(showError); });
  function showError(error: unknown) {
    dispose(); container.innerHTML = `<div class="strategy-warning" role="alert"><p>${esc((error as Error).message)}</p><button id="study-load-retry" class="button">Reintentar</button></div>`;
    container.querySelector('#study-load-retry')!.addEventListener('click', () => void render().catch(showError));
  }
  await load();
  return { share, resize: () => { priceChart?.resize(); orbitChart?.resize(); resultCharts.forEach(c=>c.resize()); drawCase(); } };
}
