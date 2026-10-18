// Read-only extraction for the browser tool's evaluate(). No application internals.
// Supply this function to evaluate, then save returned DOM observations locally.
// Check clamped heads against small circles in a later tail before accepting them.
export function readVisibleSVG() {
  const svgs = document.querySelectorAll('svg');
  const benchmark = svgs[0], rotation = svgs[1];
  const ticks = (selector, attribute) => [...rotation.querySelectorAll(selector)]
    .filter(t => /^\d+(\.\d+)?$/.test(t.textContent))
    .map(t => [+t.textContent, +t.getAttribute(attribute)]);
  const xs = ticks('g[clip-path="url(#lower-axis-clip-path)"] > text', 'dx');
  const ys = ticks('text[x="100"]', 'y');
  const slope = ts => (ts[1][1] - ts[0][1]) / (ts[1][0] - ts[0][0]);
  const sx = slope(xs), sy = slope(ys);
  const groups = [...rotation.querySelectorAll('g')];
  const tails = groups.filter(g => g.querySelectorAll(':scope > circle').length > 1);
  const heads = groups.filter(g => g.querySelector(':scope > circle') && g.querySelector(':scope > text'));
  return {
    header: benchmark.textContent, price: benchmark.querySelector('text').textContent,
    ticks: { xs, ys },
    series: heads.map((g, i) => {
      const [x, y] = g.getAttribute('transform').match(/[-\d.]+/g).map(Number);
      return {
        symbol: g.textContent, headTransform: [x, y],
        coordinate: [xs[0][0] + (x - xs[0][1]) / sx, ys[0][0] + (y - ys[0][1]) / sy],
        tailCirclePixels: [...(tails[i]?.querySelectorAll('circle') ?? [])]
          .map(c => [+c.getAttribute('cx'), +c.getAttribute('cy')]),
        tailTransform: tails[i]?.parentElement.getAttribute('transform'),
      };
    }),
    prices: [...document.querySelectorAll('tbody tr')].map(r => r.textContent),
  };
}
