export const progressMarkup = `
<section id="progress-panel" class="progress-panel" role="tabpanel" aria-labelledby="progress-tab" hidden>
  <article class="progress-intro"><div class="eyebrow">18 OCT 2026 · QA DE KIKO</div>
    <h2>Qué he hecho</h2><p>De dos gráficos que no cuadraban a una fórmula semanal que reproduce la referencia con un error de milésimas.</p>
    <span class="progress-status">Aproximación validada · índices semanales frente al S&P 500</span>
  </article>
  <section class="progress-card"><span class="step-number">01</span><h3>Primero, comprobar el problema</h3>
    <p>Kiko tenía razón: comparar Nasdaq Composite con S&P 500 el 2 de enero de 2026 daba <strong>(99,61; 99,68), Rezagado</strong> en la primera versión, mientras StockCharts lo colocaba en Debilitándose. El cierre del S&P coincidía: 6.858,47. Cambiar Nasdaq 100 por Composite no resolvía la diferencia.</p>
    <p>Guardé el dataset, todos los precios locales, el código y sus hashes antes de experimentar. Así comparé fórmulas sobre los mismos precios, sin confundir un cambio de cálculo con una actualización del proveedor.</p>
  </section>
  <section class="progress-card"><span class="step-number">02</span><h3>Hacer que comparar fechas sea cómodo</h3>
    <p>Ahora puedes arrastrar la zona sombreada sobre el gráfico del benchmark. Se mantienen la cola y la sincronización de fecha, precios, tabla y trayectorias. Al intervenir se pausa la reproducción y soltar no provoca otro salto.</p>
    <p>Añadí el rango visual de un año o todo el histórico, ambos límites del intervalo, salto por fecha y <strong>Copiar esta fecha</strong>. Una fecha no negociada retrocede al periodo cerrado disponible. El enlace normal sigue abriendo los datos recientes. El rango visible no cambia los datos usados para calcular.</p>
  </section>
  <section class="progress-card"><span class="step-number">03</span><h3>Medir StockCharts, no sólo mirar la forma</h3>
    <p>Recogí 52 semanas de Nasdaq Composite y Dow Jones, ambos frente al S&P 500. Leí los puntos dibujados en su SVG y convertí las posiciones a coordenadas usando las marcas numéricas de los ejes. No son valores certificados de un tooltip: asigné una incertidumbre conservadora de ±0,01 por eje.</p>
    <p>Detecté que algunas cabezas fuera de escala se fijan al borde: usé los círculos reales de sus colas para no medir una posición falsa. Contrasté cierres, semanas festivas y la cola: diez intervalos corresponden a diez puntos anteriores más la cabeza.</p>
    <p>Reservé las últimas 16 fechas del Nasdaq y todo Dow. Las primeras 36 fechas de Nasdaq fueron el conjunto para elegir parámetros.</p>
  </section>
  <section class="progress-card"><span class="step-number">04</span><h3>La primera búsqueda mejoraba, pero no bastaba</h3>
    <p>Probé 5.160 variantes de medias exponenciales —EMA—. La mejor reducía el error alrededor del 60 %, pero dejaba RMSE de 0,39–0,81 por eje y sólo 66,7–72,5 % de cuadrantes correctos. No superó los umbrales de 0,20 y 95 %. Esa candidata no se publicó como cálculo.</p>
    <p>Una línea más suave no prueba que una fórmula sea mejor. Comparé puntos por fecha, diferencias X/Y, cuadrantes y cruces de 100, sin suavizado gráfico.</p>
  </section>
  <section class="progress-card formula-card"><span class="step-number">05</span><h3>La pista decisiva: medias simples</h3>
    <p>Al ampliar la búsqueda, las <strong>medias móviles simples —SMA—</strong> encajaron mucho mejor. Una SMA es la media aritmética de los últimos N cierres. Esta es la fórmula inferida y ahora utilizada en la vista semanal de índices frente al S&P 500:</p>
    <div class="formula-block"><code>RSₜ = cierre del activoₜ / cierre del benchmarkₜ</code><code>Xₜ = 100 × SMA(RS, 10)ₜ / SMA(RS, 30)ₜ</code><code>Yₜ = 100 × Xₜ / SMA(X, 9)ₜ</code></div>
    <p>Las ventanas incluyen el punto actual y sólo semanas anteriores. Todos los activos comparten los parámetros 10/30/9. <strong>No hay correcciones por ticker, fecha, ni escalas ajustadas.</strong> El cálculo necesita 38 observaciones semanales comunes; conservamos 50 iniciales fuera de la vista para mantener la fecha de inicio anterior.</p>
    <p>La búsqueda comparó EMA y SMA, medias paralelas y encadenadas, y alternativas de momentum. Las escalas estimadas en ajuste eran prácticamente 1: se retiraron antes de la confirmación nueva.</p>
  </section>
  <section class="progress-card"><span class="step-number">06</span><h3>Comprobar que funciona fuera del ajuste</h3>
    <p>Nasdaq reservado y Dow ya se habían examinado al evaluar la primera ronda: sus comprobaciones se reutilizan y no las presento como una segunda prueba ciega. Para tener una confirmación nueva, <strong>fijé la fórmula y después recogí 52 semanas de NYSE Composite</strong>, que no se usaron para elegirla.</p>
    <div class="progress-table"><table><thead><tr><th>Conjunto</th><th>Fechas</th><th>RMSE X</th><th>RMSE Y</th><th>Cuadrantes*</th></tr></thead><tbody>
      <tr><td>Nasdaq · últimas fechas</td><td>16</td><td>0,0033</td><td>0,0027</td><td>100 %</td></tr>
      <tr><td>Dow Jones · completo</td><td>52</td><td>0,0028</td><td>0,0029</td><td>100 %</td></tr>
      <tr><td>NYSE Composite · confirmación nueva</td><td>52</td><td>0,0066</td><td>0,0045</td><td>100 %</td></tr>
    </tbody></table></div>
    <p class="progress-note">* Se excluyen observaciones cuya incertidumbre alcanza un eje; también se analizan aparte las que están a menos de 0,10. RMSE es la raíz del error cuadrático medio, en puntos del gráfico. Reducción superior al 99,7 % frente al cálculo inicial en estos conjuntos.</p>
    <p>Los puntos de Nasdaq y Dow encajan dentro del redondeo de la referencia. NYSE muestra pequeñas diferencias de cierres entre proveedores: su error máximo de coordenadas es 0,0141. No se ajustaron parámetros para corregirlo.</p>
    <figure class="comparison-figure"><a href="${import.meta.env.BASE_URL}research-comparison.png" target="_blank" rel="noopener noreferrer"><img src="${import.meta.env.BASE_URL}research-comparison.png" loading="lazy" alt="Trayectorias y series de Nasdaq, Dow y NYSE: la aproximación SMA casi se superpone con StockCharts, mientras la fórmula EMA inicial muestra diferencias claras."></a><figcaption>Referencia en negro, SMA en azul discontinuo y primera fórmula EMA en naranja. Pulsa para ampliar.</figcaption></figure>
    <div class="case-links"><a href="?v=1&g=indices&tf=weekly&b=GSPC&s=IXIC&tail=10&date=2026-01-02">Abrir caso 02/01/2026 → (101,46; 99,33)</a><a href="?v=1&g=indices&tf=weekly&b=GSPC&s=IXIC&tail=10&date=2026-03-20">Abrir caso 20/03/2026 → (98,85; 99,06)</a></div>
    <p>Ambos reproducen el cuadrante y el sentido del último tramo de Kiko. Las pruebas comprueban además causalidad, invariancia de escala, benchmark contra sí mismo en (100,100), festivos y ausencia de datos.</p>
  </section>
  <section class="progress-card"><span class="step-number">07</span><h3>Qué significa este resultado y qué queda abierto</h3>
    <p><strong>Es una aproximación empírica muy fiel en la muestra comprobada; no una revelación del código propietario JdK.</strong> La documentación original no publica sus fórmulas. Los datos disponibles no permiten demostrar que esta implementación sea idéntica para todos los activos, periodos, proveedores o versiones de StockCharts.</p>
    <p>La sustitución cubre sólo índices semanales frente al S&P 500. Diario, sectores y otros benchmarks siguen usando la fórmula EMA independiente anterior. El método y los parámetros viajan identificados en cada vista del dataset. Conservamos la versión anterior y sus precios para reproducir y recuperar resultados.</p>
    <p>Quedan por comprobar otros periodos históricos y universos. La validación semanal no demuestra paridad diaria ni autoriza a trasladar automáticamente estos parámetros a otro cálculo.</p>
    <p>Fuentes: <a href="https://stockcharts.com/freecharts/rrg/" target="_blank" rel="noopener noreferrer">gráfico de StockCharts</a>, <a href="https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts" target="_blank" rel="noopener noreferrer">ayuda de navegación</a> y <a href="https://relativerotationgraphs.com/wp-content/uploads/2024/10/Relative-Rotation-Graph-Thomson-Reuters-Guide.pdf" target="_blank" rel="noopener noreferrer">guía de RRG</a>. El repositorio conserva los protocolos y el banco de experimentos; el feedback privado y sus capturas permanecen locales.</p>
  </section>
</section>`;
