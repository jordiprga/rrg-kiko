import { initChart, type Chart } from './charts';
import * as echarts from 'echarts/core';
import { LegendComponent } from 'echarts/components';
import { entryNames, type StrategyState } from './strategies-model';

echarts.use([LegendComponent]);

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const pct = (n: number | null | undefined) => n == null || !Number.isFinite(n) ? '—' : `${(n*100).toLocaleString('es-ES',{maximumFractionDigits:2})} %`;
const pvalue = (n: number | null | undefined) => n == null ? '—' : n.toLocaleString('es-ES',{maximumFractionDigits:4});
const num = (n: number | null | undefined) => n == null || !Number.isFinite(n) ? '—' : n.toLocaleString('es-ES',{maximumFractionDigits:2});
export const exitName = (id: string) => ({orbit:'Líder → Debilitándose','time-4':'4 semanas','time-13':'13 semanas','time-26':'26 semanas','time-52':'52 semanas'} as Record<string,string>)[id]
  ?? id.replace('pct-','Trailing ').replace(/(10|15|20)(?=\+|$)/,'$1 %').replace('atr-','ATR × ').replace('+orbit',' + órbita');
const allocationName = (id: string) => ({'equal-20':'20 posiciones · reparto igual','inverse-vol-20':'20 posiciones · menor peso a mayor volatilidad','ranked-10':'10 posiciones · prioridad a mayor fuerza'} as Record<string,string>)[id];

export interface ResearchControls { period: string; exit: string; capital: number; mode: 'entries'|'allocation'; selected: string; }
export function researchControls(search=location.search): ResearchControls {
  const p=new URLSearchParams(search);
  const mode=p.get('mode')==='entries'?'entries':'allocation';
  const period=['train','validation','test','all'].includes(p.get('period')??'')?p.get('period')!:'test';
  return {period:mode==='allocation'&&period==='all'?'test':period,
    exit:p.get('exit')??'time-13',capital:Math.max(100,Math.min(1e9,Number(p.get('capital'))||100000)),
    mode,selected:p.get('portfolio')??''};
}
function metricCards(m: any, capital: number) {
  return `<div class="strategy-metrics quant-metrics">${[
    [pct(m?.cagr),'CAGR · rentabilidad anual compuesta'],[num(m?.sharpe),'Sharpe · tipo libre de riesgo 0 %'],
    [pct(m?.maxDrawdown),'Mayor caída desde un máximo'],[num(m?.sortino),'Sortino · riesgo a la baja'],
    [pct(m?.annualVolatility),'Volatilidad anual'],[m?.totalReturn!=null?`${(capital*(1+m.totalReturn)).toLocaleString('es-ES',{maximumFractionDigits:0})} USD`:'—','Capital final simulado'],
  ].map(([value,label])=>`<div><strong>${value}</strong><span>${label}</span></div>`).join('')}</div>`;
}
export function currentResultsMarkup(report: any, state: StrategyState, controls: ResearchControls): string {
  if (report.version!==2 || report.scope!=='current-constituents' || !Array.isArray(report.variants) || !report.allocations) throw new Error('Estudio actual incompatible');
  const a=report.allocations;
  const selected=a.candidates.find((c:any)=>c.id===controls.selected)??a.candidates.find((c:any)=>c.id===a.selectedId);
  if (selected) controls.selected=selected.id;
  const m=selected?.periods[controls.period==='all'?'test':controls.period];
  const rows=report.variants.filter((r:any)=>r.reference===state.reference&&r.confirmation===state.confirmation&&r.sectorFilter===state.strong
    &&(r.volumeFilter!=null)===state.volume&&(state.rule==='all'||r.rule===state.rule)&&(controls.exit==='all'||r.exitRule===controls.exit));
  const benchmark=controls.period==='all'?report.benchmark:report.benchmarkPeriods[controls.period];
  const cohort=report.cohortBenchmarkPeriods?.[controls.period==='all'?'test':controls.period];
  const candidates=[...a.candidates].sort((x:any,y:any)=>(y.selectionScore??-1e9)-(x.selectionScore??-1e9));
  return `<section class="strategy-card quant-intro"><p class="strategy-eyebrow">S&P 500 · COMPONENTES ACTUALES</p><h3>Del giro a una cartera medible</h3>
    <p><strong>${report.universeCount} valores de ${report.companyCount} empresas</strong>, composición del ${esc(report.asOf)}. Se estudia el historial disponible de estas acciones desde 2010, incluso antes de su incorporación al índice. Las nuevas cotizadas entran cuando tienen calentamiento suficiente.</p>
    <div class="quant-timeline"><div><strong>In sample · 2010–2018</strong><span>Elegir tres candidatos con Sharpe anual de 2016–2018.</span></div><div><strong>Validación · 2019–2022</strong><span>Elegir uno de esos tres sin consultar la prueba final.</span></div><div><strong>Out of sample · 2023–${esc(report.latestSession.slice(0,4))}</strong><span>Reglas fijadas; mostrar resultado, aunque salga mal.</span></div></div>
    <p class="strategy-note">Separación temporal retrospectiva: el universo se conoce hoy y tiene sesgo de supervivencia. La idea surgió de ejemplos conocidos de 2025, incluidos en este histórico: no es un holdout ciego ni una prueba prospectiva independiente.</p>
    <div class="quant-controls"><label>Qué comparar<select id="quant-mode"><option value="allocation" ${controls.mode==='allocation'?'selected':''}>Carteras · selección y reparto de capital</option><option value="entries" ${controls.mode==='entries'?'selected':''}>Entradas y salidas · misma asignación</option></select></label>
      <label>Periodo<select id="quant-period">${[['test','Out of sample · 2023 en adelante'],['validation','Validación · 2019–2022'],['train','In sample · 2010–2018'],...(controls.mode==='entries'?[['all','Histórico completo · descriptivo']]:[])].map(([v,label])=>`<option value="${v}" ${v===controls.period?'selected':''}>${label}</option>`).join('')}</select></label>
      <label>Capital inicial simulado · USD<input id="quant-capital" type="number" min="100" max="1000000000" step="1000" value="${controls.capital}"></label></div>
    <p class="strategy-note">El capital escala el resultado; no altera los pesos ni modela impacto de mercado, impuestos, lotes enteros o la capacidad para gestionar grandes importes.</p><button class="strategy-link" id="quant-download">Descargar métricas de las carteras · CSV ↓</button></section>
    ${controls.mode==='allocation'?`<section class="strategy-card"><p class="strategy-eyebrow">MODELO ELEGIDO CON ENTRENAMIENTO Y VALIDACIÓN</p><h3>Cómo se reparte el capital</h3>
      <label class="quant-wide">Cartera a explorar<select id="quant-portfolio">${candidates.map((c:any)=>`<option value="${c.id}" ${c.id===controls.selected?'selected':''}>${c.id===a.selectedId?'★ Elegida sin usar test · ':''}${esc(entryNames[c.policy.rule])} · ${esc(exitName(c.policy.exitRule))} · ${esc(allocationName(c.policy.allocation))}${c.policy.sectorFilter?' · sector fuerte':''}${c.policy.regime?' · filtro índices':''}</option>`).join('')}</select></label>
      <p>${selected?`${esc(entryNames[selected.policy.rule])}; salida: ${esc(exitName(selected.policy.exitRule))}. ${esc(allocationName(selected.policy.allocation))}. Máximo ${(selected.policy.stockCap*100)} % por acción y 25 % por sector al rebalancear. ${selected.policy.sectorFilter?'Sólo sectores en Líder.':''} ${selected.policy.regime?'Exige mercado favorable según los ETFs de los índices; en caso contrario, pasa a efectivo.':'Sin filtro de mercado amplio.'}`:''}</p>
      <p>Compra señales nuevas a la siguiente apertura, prioriza X + Y si coinciden más candidatos que plazas y mantiene efectivo en las plazas libres. Reequilibra cada semana y cuando hay entradas o salidas. Cada posición conserva su salida inicial.</p>
      ${metricCards(m,controls.capital)}<p>SPY en las mismas fechas: CAGR <strong>${pct(benchmark?.cagr)}</strong> · Sharpe ${num(benchmark?.sharpe)} · caída máxima ${pct(benchmark?.maxDrawdown)}.</p>
      <p>Control sin señal: cartera equiponderada de estos componentes actuales, con 252 sesiones de calentamiento y el mismo coste de rebalanceo. CAGR <strong>${pct(cohort?.cagr)}</strong> · Sharpe ${num(cohort?.sharpe)} · caída máxima ${pct(cohort?.maxDrawdown)}. Este control comparte el sesgo de supervivencia y ayuda a separar el efecto de las señales del universo escogido.</p>
      <p class="quant-reading"><strong>Lectura del periodo:</strong> ${m?.status!=='ok'?'Faltan datos para valorar esta cartera.':m.sharpe>benchmark?.sharpe&&m.cagr>benchmark?.cagr?'Esta variante supera a SPY tanto en crecimiento como en Sharpe durante este periodo. Hay que comprobar también el control del mismo universo, los costes y los demás periodos.':m.sharpe>benchmark?.sharpe?'Mejora el Sharpe de SPY, pero no su crecimiento anual. El interés sería reducir riesgo, no afirmar mayor rentabilidad.':'Esta variante no mejora el Sharpe de SPY durante este periodo. Un resultado positivo por sí solo no demuestra una ventaja.'} ${selected?.id!==a.selectedId?'Has elegido otra variante después de la selección inicial; esta exploración no sustituye la prueba del modelo fijado.':''}</p>
      <div id="quant-curve" class="strategy-result-curve" role="img" aria-label="Capital de la cartera y SPY en el periodo elegido"></div><div id="quant-holdings"></div>
      <p>${m?.closedTrades??0} salidas · ${m?.openTrades??0} posiciones abiertas · exposición media ${pct(m?.meanExposure)} · posiciones medias ${num(m?.meanPositions)}. Tipo libre de riesgo y efectivo 0 %; costes 10 pb por lado y rebalanceo.</p>
      <h4>¿Se mantiene con otros costes? · cartera elegida, out of sample</h4><div class="strategy-table-scroll"><table><thead><tr><th>Coste por lado</th><th>CAGR</th><th>Sharpe</th><th>Caída máxima</th></tr></thead><tbody>${Object.entries(a.costStress).map(([c,v]:[string,any])=>`<tr><td>${c} pb</td><td>${pct(v.cagr)}</td><td>${num(v.sharpe)}</td><td>${pct(v.maxDrawdown)}</td></tr>`).join('')}</tbody></table></div>
      <details><summary>Las ${a.candidateCount} variantes probadas · ordenadas por criterio in sample</summary><p>La tabla conserva todos los ensayos. Elegir otra tras mirar su resultado de test lo convertiría en exploración, no en una nueva prueba independiente.</p><div class="strategy-table-scroll"><table><thead><tr><th>Cartera</th><th>Sharpe in sample</th><th>Sharpe validación</th><th>CAGR test</th><th>Sharpe test</th><th>Caída test</th></tr></thead><tbody>${candidates.map((c:any)=>`<tr><td>${c.id===a.selectedId?'★ ':''}${esc(entryNames[c.policy.rule])}<small>${esc(exitName(c.policy.exitRule))} · ${esc(allocationName(c.policy.allocation))} · sector ${c.policy.sectorFilter?'sí':'no'} · índices ${c.policy.regime?'sí':'no'}</small></td><td>${num(c.periods.train.sharpe)}</td><td>${num(c.periods.validation.sharpe)}</td><td>${pct(c.periods.test.cagr)}</td><td>${num(c.periods.test.sharpe)}</td><td>${pct(c.periods.test.maxDrawdown)}</td></tr>`).join('')}</tbody></table></div></details>
      <details><summary>Walk-forward · elegir con el pasado y aplicar al siguiente año</summary><p>Cinco años anteriores; selección por mediana del Sharpe de los tres últimos años, tolerancia 0,05 y desempate por caída máxima. La nueva política controla nuevas compras; las posiciones previas conservan su salida. Es una cartera distinta de la elegida mediante el corte fijo.</p>${metricCards(a.walkForward.metrics,controls.capital)}<div id="quant-walk-curve" class="strategy-result-curve" role="img" aria-label="Capital en evaluación móvil"></div><div class="strategy-table-scroll"><table><thead><tr><th>Año aplicado</th><th>Datos usados hasta</th><th>Regla seleccionada</th></tr></thead><tbody>${a.walkForward.folds.map((f:any)=>{const c=a.candidates.find((c:any)=>c.id===f.chosen);return `<tr><td>${f.year}</td><td>${esc(f.trainingEnd)}</td><td>${esc(entryNames[c?.policy.rule])} · ${esc(exitName(c?.policy.exitRule??''))} · ${esc(allocationName(c?.policy.allocation??''))}</td></tr>`;}).join('')}</tbody></table></div></details>
    </section>`:`<section class="strategy-card"><h3>¿Qué entradas y salidas funcionan mejor?</h3><p>La asignación es idéntica en todas las filas: posiciones activas equiponderadas cada apertura, sin piramidar, con costes de rebalanceo. Así se separa el efecto de la entrada y la salida del método de asignación.</p>
      <label class="quant-wide">Salida<select id="quant-exit"><option value="all">Todas las salidas</option>${report.protocol.exits.map((id:string)=>`<option value="${id}" ${id===controls.exit?'selected':''}>${esc(exitName(id))}</option>`).join('')}</select></label>
      <p>SPY: CAGR ${pct(benchmark?.cagr)} · Sharpe ${num(benchmark?.sharpe)} · caída máxima ${pct(benchmark?.maxDrawdown)}.</p><div class="strategy-table-scroll"><table id="quant-entry-table"><thead><tr><th>Entrada / salida</th><th>CAGR</th><th>Sharpe</th><th>Sortino</th><th>Caída máxima</th><th>Positivas</th><th>Cerradas</th><th></th></tr></thead><tbody>${rows.map((r:any)=>{const p=controls.period==='all'?r.portfolio:r.periods[controls.period];const s=controls.period==='all'?r.summary:p.trades;return `<tr><td>${esc(entryNames[r.rule])}<small>${esc(exitName(r.exitRule))}</small></td><td>${pct(p.cagr)}</td><td>${num(p.sharpe)}</td><td>${num(p.sortino)}</td><td>${pct(p.maxDrawdown)}</td><td>${pct(s.winRate)}</td><td>${s.closed}<small>${s.open} abiertas · ${s.missing} sin datos</small></td><td><button class="strategy-link" data-quant-curve="${esc(r.detailsUrl)}">Ver curva</button></td></tr>`;}).join('')}</tbody></table></div>
      <div id="quant-curve" class="strategy-result-curve" role="img" aria-label="Capital por estrategia y SPY"></div>
      <h4>¿Hay señal estadística en las entradas?</h4><p>Se compara el exceso neto a 13 semanas contra SPY, manteniendo las mismas fechas. El intervalo del 95 % usa bloques de 52 semanas para respetar que muchas señales ocurren juntas. Las ocho comparaciones principales reciben corrección de Holm.</p>
      <div class="strategy-table-scroll"><table><thead><tr><th>Entrada</th><th>Exceso medio a 13 semanas</th><th>Intervalo 95 %</th><th>p ajustada</th><th>Lectura</th></tr></thead><tbody>${report.variants.filter((r:any)=>r.exitRule==='time-13'&&r.reference===state.reference&&r.confirmation===1&&!r.sectorFilter&&r.volumeFilter==null).map((r:any)=>{const e=controls.period==='all'?r.entryEvidence:r.entryEvidencePeriods[controls.period];const adjusted=controls.period==='all'?r.adjustedPValue:r.adjustedPValuePeriods?.[controls.period];const yes=e.interval?.[0]>0&&adjusted!=null&&adjusted<.05;return `<tr><td>${esc(entryNames[r.rule])}</td><td>${pct(e.mean)}</td><td>${e.interval?e.interval.map(pct).join(' a '):'Insuficiente'}</td><td>${pvalue(adjusted)}</td><td>${yes?'Asociación histórica positiva':'Ventaja no demostrada'}<small>Periodo elegido · exploratorio</small></td></tr>`;}).join('')}</tbody></table></div></section>`}
    <section class="strategy-card"><h3>Qué mide cada cifra</h3><p><strong>CAGR</strong>: crecimiento anual compuesto del capital, incluyendo días en efectivo. <strong>Sharpe</strong>: media diaria dividida por su desviación y anualizada con √252. <strong>Sortino</strong>: penaliza sólo el retorno diario negativo. <strong>Caída máxima</strong>: peor pérdida desde un máximo anterior. No se calcula CAGR encadenando operaciones solapadas.</p>
      <p>La hipótesis es que el giro de fuerza relativa anticipa una mejora posterior. Para hablar de una ventaja interesa que el resultado posterior supere controles sencillos, resista costes y no dependa de una sola acción, sector o época. Un Sharpe alto en entrenamiento no basta.</p>
      <details><summary>Cobertura, supuestos y reproducción</summary>${report.limitations.map((s:string)=>`<p>${esc(s)}</p>`).join('')}<p>${esc(a.indexRegime)}</p><p>Los índices no se compran directamente: SPY, QQQ, DIA e IWM son proxies negociables. Los datos OHLCV quedan fuera del sitio; se publican cálculos derivados y precios indexados.</p><p>Protocolo ${esc(report.protocolHash)}<br>Datos ${esc(report.snapshotHash)}<br>Código ${esc(report.engineHash)}</p>${report.sources.map((s:any)=>`<p><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a></p>`).join('')}<div class="strategy-table-scroll"><table><thead><tr><th>Valor</th><th>Desde</th><th>Hasta</th><th>Sesiones</th></tr></thead><tbody>${report.coverage.map((r:any)=>`<tr><td>${esc(r.ticker)}</td><td>${esc(r.first)}</td><td>${esc(r.last)}</td><td>${r.sessions}${r.corrections?.length?` · ${r.corrections.length} rango corregido`:""}</td></tr>`).join('')}</tbody></table></div></details></section>`;
}

export async function bindCurrentResults(container: HTMLElement,report: any,controls: ResearchControls,fetchJson:(p:string)=>Promise<any>,rerender:()=>Promise<void>,charts: Chart[],isCurrent:()=>boolean=()=>true) {
  const update=async()=>{
    const p=new URLSearchParams(location.search);
    for (const [key,value] of Object.entries({period:controls.period,exit:controls.exit,capital:String(controls.capital),mode:controls.mode,portfolio:controls.selected})) p.set(key,value);
    history.replaceState(null,'',`${location.pathname}?${p}#estrategias`); await rerender();
  };
  container.querySelector('#quant-download')?.addEventListener('click',()=>{
    const columns=['id','entrada','salida','asignacion','sector_fuerte','filtro_indices','periodo','inicio','fin','CAGR','Sharpe','Sortino','caida_maxima','volatilidad','rentabilidad_total','exposicion_media','rotacion','seleccionada_sin_test'];
    const rows=[columns,...report.allocations.candidates.flatMap((c:any)=>Object.entries(c.periods).map(([period,m]:[string,any])=>[
      c.id,entryNames[c.policy.rule],exitName(c.policy.exitRule),allocationName(c.policy.allocation),c.policy.sectorFilter,c.policy.regime,period,
      m.start,m.end,m.cagr,m.sharpe,m.sortino,m.maxDrawdown,m.annualVolatility,m.totalReturn,m.meanExposure,m.turnover,c.id===report.allocations.selectedId]))];
    const csv='\uFEFF'+rows.map((row: unknown[])=>row.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(';')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=`orbita-carteras-${report.asOf}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  for (const id of ['period','mode','exit','capital','portfolio']) container.querySelector<HTMLInputElement>('#quant-'+id)?.addEventListener('change',async e=>{
    const value=(e.target as HTMLInputElement).value;
    if (id==='capital') controls.capital=Math.max(100,Math.min(1e9,Number(value)||100000));
    else if(id==='portfolio') controls.selected=value;
    else if(id==='mode') {controls.mode=value as ResearchControls['mode'];if(controls.period==='all')controls.period='test';}
    else (controls as any)[id]=value;
    await update();
  });
  const benchmark=await fetchJson(report.benchmarkUrl);
  if(!isCurrent())return;
  const draw=(element: HTMLElement,curve: [string,number][],comparison?:[string,number][])=>{
    const chart=initChart(element); charts.push(chart);
    const spy=new Map(comparison??[]);
    chart.setOption({animation:false,legend:{data:comparison?['Cartera','SPY']:['Cartera']},tooltip:{trigger:'axis',confine:true},
      grid:{left:70,right:20,top:45,bottom:35},xAxis:{type:'category',data:curve.map(p=>p[0])},yAxis:{type:'value',scale:true},
      series:[{name:'Cartera',type:'line',showSymbol:false,data:curve.map(p=>p[1]*controls.capital)},...(comparison?[{name:'SPY',type:'line',showSymbol:false,data:curve.map(p=>spy.has(p[0])?spy.get(p[0])!*controls.capital:null),connectNulls:true}]:[])]});
  };
  const b=controls.period==='all'?benchmark.equity:benchmark.periods[controls.period];
  if(controls.mode==='allocation') {
    const selected=report.allocations.candidates.find((c:any)=>c.id===controls.selected);
    if(selected) {
      const detail=await fetchJson(selected.detailsUrl); if(!isCurrent())return; const period=detail.periods[controls.period==='all'?'test':controls.period];
      const element=container.querySelector<HTMLElement>('#quant-curve'); if(!element?.isConnected)return;
      draw(element,period.equity,b);
      const last=period.snapshots.at(-1);const endEquity=last?.capitalIndex??period.equity.at(-1)?.[1]??1;
      const target=container.querySelector('#quant-holdings');
      if(last&&target)target.innerHTML=`<details><summary>Asignación registrada · ${esc(last.date)} · efectivo ${pct(last.cash)}</summary><p>Pesos objetivo de esa apertura; los pesos pueden variar entre rebalanceos. Importes a esa apertura, después de costes, sobre el capital simulado.</p><div class="strategy-table-scroll"><table><thead><tr><th>Acción</th><th>Sector actual</th><th>Peso</th><th>Importe simulado</th><th>Señal</th><th>Salida</th></tr></thead><tbody>${last.positions.map((p:any)=>`<tr><td>${esc(p.ticker)}</td><td>${esc(p.sector)}</td><td>${pct(p.weight)}</td><td>${num(p.weight*endEquity*controls.capital)} USD</td><td>${esc(p.signalDate)}</td><td>${esc(exitName(p.exitRule))}</td></tr>`).join('')}</tbody></table></div></details>`;
    }
    const walk=container.querySelector<HTMLElement>('#quant-walk-curve');
    if(walk) {const d=await fetchJson(report.allocations.walkForward.detailsUrl); if(walk.isConnected&&isCurrent())draw(walk,d.equity);}
  } else {
    container.querySelectorAll<HTMLButtonElement>('[data-quant-curve]').forEach(button=>button.addEventListener('click',async()=>{
      const data=await fetchJson(button.dataset.quantCurve!);const curve=controls.period==='all'?data.equity:data.periods[controls.period];
      if(!isCurrent())return;
      const element=container.querySelector<HTMLElement>('#quant-curve');if(!element?.isConnected)return;
      const old=charts.find(c=>c.getDom()===element);old?.dispose();draw(element,curve,b);element.scrollIntoView({block:'center',behavior:'smooth'});
    }));
  }
}
