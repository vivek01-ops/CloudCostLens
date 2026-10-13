import type { EChartsOption } from "echarts";

/** Shared ECharts theme matching the CloudCostLens design tokens. */

export const CHART_PALETTE = ["#4F8CFF", "#37C8E8", "#32B67A", "#E8AA43", "#E66B72", "#A5B1C5"];

export const chartBase: EChartsOption = {
  backgroundColor: "transparent",
  textStyle: { color: "#A5B1C5", fontFamily: "ui-sans-serif, system-ui, sans-serif" },
  color: CHART_PALETTE,
  tooltip: {
    trigger: "axis",
    backgroundColor: "#0E1528",
    borderColor: "#283449",
    textStyle: { color: "#F3F6FC", fontSize: 12 },
    axisPointer: { lineStyle: { color: "#283449" } },
  },
  legend: {
    textStyle: { color: "#A5B1C5", fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
    icon: "circle",
  },
  grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
  xAxis: {
    type: "category",
    axisLine: { lineStyle: { color: "#283449" } },
    axisTick: { show: false },
    axisLabel: { color: "#A5B1C5", fontSize: 11 },
  },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#1B2440" } },
    axisLabel: { color: "#A5B1C5", fontSize: 11 },
  },
};

export function moneyAxisFormatter(currency = "USD"): (value: number) => string {
  const fmt = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  });
  return (value: number) => fmt.format(value);
}