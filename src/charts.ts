import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent, DataZoomComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import { quadrants, type Point } from './model';

echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent, DataZoomComponent, CanvasRenderer]);
export const palette = ['#356c89', '#aa6b3e', '#7d65a6', '#3c8276', '#b65070', '#7e873a', '#567bd0', '#a45c48', '#9580b0', '#368b9b', '#947348', '#5e8c58', '#a95894', '#638492', '#be8158', '#62765e', '#a37d26', '#5d63a4'];
export const initChart = (element: HTMLElement) => echarts.init(element, undefined, { renderer: 'canvas' });
export type Chart = ReturnType<typeof initChart>;
export interface PlotAsset { id: string; name: string; color: string; points: Point[]; faded: boolean }
const escape = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

export function rotationOptions(assets: PlotAsset[], bounds: number[], arrows: boolean, benchmark: string, resetZoom: boolean): EChartsCoreOption {
  const [minX, maxX, minY, maxY] = bounds;
  const area = (name: string, color: string, x1: number, y1: number, x2: number, y2: number) =>
    [{ name, xAxis: x1, yAxis: y1, itemStyle: { color } }, { xAxis: x2, yAxis: y2 }];
  const series: any[] = [{
    id: 'quadrants', type: 'line', data: [], silent: true,
    markArea: { silent: true, label: { color: '#637267', fontSize: 11, fontWeight: 600, position: 'insideTopLeft', padding: [12, 12] }, data: [
      area('MEJORANDO', quadrants.improving.fill, minX, 100, 100, maxY),
      area('LÍDER', quadrants.leading.fill, 100, 100, maxX, maxY),
      area('REZAGADO', quadrants.lagging.fill, minX, minY, 100, 100),
      area('DEBILITÁNDOSE', quadrants.weakening.fill, 100, minY, maxX, 100),
    ] },
    markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#a9b6aa', width: 1, type: 'solid' }, data: [{ xAxis: 100 }, { yAxis: 100 }] },
  }];
  for (const asset of assets) {
    const last = asset.points.at(-1);
    if (!last) continue;
    const opacity = asset.faded ? 0.15 : 1;
    const data = asset.points.map((p, i) => ({ value: [p[1], p[2], p[0], p[3]], itemStyle: { opacity: opacity * (0.2 + 0.8 * i / Math.max(1, asset.points.length - 1)) } }));
    series.push({
      id: `${asset.id}-trail`, name: asset.id, type: 'line', data,
      symbol: 'circle', symbolSize: 4, showSymbol: true, smooth: false,
      lineStyle: { color: asset.color, width: 2, opacity: opacity * 0.7 }, itemStyle: { color: asset.color },
      animation: false,
      markLine: {
        silent: true, symbol: ['none', 'arrow'], symbolSize: [0, 9], label: { show: false },
        lineStyle: { color: asset.color, opacity, width: 2, type: 'solid' },
        data: arrows && asset.points.length > 1 ? [[{ coord: asset.points.at(-2)!.slice(1, 3) }, { coord: last.slice(1, 3) }]] : [],
      },
    });
    series.push({
      id: `${asset.id}-head`, name: asset.id, type: 'scatter', data: [[last[1], last[2], last[0], last[3]]], symbolSize: 11,
      itemStyle: { color: asset.color, borderColor: '#fff', borderWidth: 2, opacity }, z: 8,
      label: { show: !asset.faded, formatter: asset.id, position: 'right', distance: 9, color: '#293e36', fontSize: 11, fontWeight: 700,
        backgroundColor: '#ffffffc9', borderRadius: 4, padding: [3, 5] },
      labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
    });
  }
  const lookup = new Map(assets.map(a => [a.id, a]));
  return {
    animation: false,
    grid: { left: 58, right: 34, top: 15, bottom: 48 },
    tooltip: { trigger: 'item', confine: true, backgroundColor: '#fff', borderColor: '#dfe5db', textStyle: { color: '#263c33', fontSize: 12 },
      formatter: (p: any) => {
        const a = lookup.get(p.seriesName); if (!a) return '';
        const v = p.value; const x = Number(v[0]), y = Number(v[1]);
        const quadrantName = x === 100 || y === 100 ? 'En el eje' : x > 100 ? y > 100 ? 'Líder' : 'Debilitándose' : y > 100 ? 'Mejorando' : 'Rezagado';
        return `<b>${escape(a.id)} · ${escape(a.name)}</b><br>${escape(v[2])} · frente a ${escape(benchmark)}<br>Fuerza relativa: <b>${x.toFixed(2)}</b><br>Momentum: <b>${y.toFixed(2)}</b><br>${quadrantName}`;
      } },
    xAxis: { type: 'value', name: 'Fuerza relativa →', nameLocation: 'middle', nameGap: 28, min: minX, max: maxX,
      nameTextStyle: { color: '#59685e', fontSize: 11 }, axisLabel: { color: '#5c6d60', fontSize: 10, formatter: (v: number) => v.toFixed(1) }, splitLine: { lineStyle: { color: '#d8e0d34d' } }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', name: 'Momentum relativo →', nameLocation: 'middle', nameGap: 42, min: minY, max: maxY,
      nameTextStyle: { color: '#59685e', fontSize: 11 }, axisLabel: { color: '#5c6d60', fontSize: 10, formatter: (v: number) => v.toFixed(1) }, splitLine: { lineStyle: { color: '#d8e0d34d' } }, axisLine: { show: false }, axisTick: { show: false } },
    dataZoom: [0, 1].map(axis => ({ id: `rotation-zoom-${axis}`, type: 'inside', ...(axis === 0 ? { xAxisIndex: 0 } : { yAxisIndex: 0 }),
      filterMode: 'none', moveOnMouseMove: true, moveOnMouseWheel: false, zoomOnMouseWheel: true, ...(resetZoom ? { start: 0, end: 100 } : {}) })),
    series,
  };
}

export function benchmarkOptions(series: [string, number][], end: number, tail: number, name: string, visible: [number, number]): EChartsCoreOption {
  const start = Math.max(0, end - tail);
  return {
    animation: false, grid: { left: 7, right: 7, top: 12, bottom: 42 },
    tooltip: { trigger: 'axis', confine: true, formatter: (p: any) => `${escape(name)} · ${escape(series[Math.round(p[0].value[0])]?.[0] ?? '')}<br>${Number(p[0].value[1]).toLocaleString('es-ES', { maximumFractionDigits: 2 })}` },
    xAxis: [{ type: 'value', min: visible[0], max: visible[1], show: false },
      { type: 'category', data: series.map(p => p[0]), boundaryGap: false, show: false }],
    yAxis: { type: 'value', scale: true, show: false,
      min: Math.min(...series.slice(visible[0], visible[1] + 1).map(p => p[1])) * 0.995,
      max: Math.max(...series.slice(visible[0], visible[1] + 1).map(p => p[1])) * 1.005 },
    series: [{ type: 'line', data: series.map((p, i) => [i, p[1]]), showSymbol: false, lineStyle: { color: '#8faaa0', width: 1.5 },
      areaStyle: { color: '#e5ece5', opacity: 0.35 },
      markArea: { silent: true, itemStyle: { color: '#456f5924' }, data: [[{ xAxis: start }, { xAxis: end }]] },
      markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#476e59', type: 'solid', width: 1 }, data: [{ xAxis: start }, { xAxis: end }] },
    }],
    dataZoom: [{ id: 'history', type: 'slider', xAxisIndex: 1, filterMode: 'none', bottom: 6, height: 20, brushSelect: false,
      zoomLock: true, handleSize: 0, moveHandleSize: 8, showDetail: false, showDataShadow: false, borderColor: '#dfe5db',
      backgroundColor: '#f2f4ee', fillerColor: '#7fa28b55', moveHandleStyle: { color: '#567c64' },
      start: 100 * start / (series.length - 1), end: 100 * end / (series.length - 1),
    }],
  };
}
