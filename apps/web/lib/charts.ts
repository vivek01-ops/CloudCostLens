import type { EChartsOption } from "echarts";

import { CHART_PALETTE, chartBase, moneyAxisFormatter } from "./chart-theme";
import type { CostPoint, OpportunityCategory, SpendByService } from "./types";

const usd = moneyAxisFormatter("USD");

export function spendTrendOption(points: CostPoint[]): EChartsOption {
  return {
    ...chartBase,
    tooltip: { ...chartBase.tooltip, valueFormatter: (v) => usd(Number(v)) },
    xAxis: { ...(chartBase.xAxis as object), type: "category", data: points.map((p) => p.date) },
    yAxis: { ...(chartBase.yAxis as object), type: "value", axisLabel: { formatter: usd } },
    series: [
      {
        name: "Daily spend",
        type: "line",
        smooth: true,
        showSymbol: false,
        lineStyle: { color: CHART_PALETTE[0], width: 2 },
        areaStyle: { color: "rgba(79,140,255,0.12)" },
        data: points.map((p) => p.amount),
      },
    ],
  };
}

export function spendByServiceOption(rows: SpendByService[]): EChartsOption {
  const sorted = [...rows].sort((a, b) => a.amount - b.amount);
  return {
    ...chartBase,
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    tooltip: { ...chartBase.tooltip, valueFormatter: (v) => usd(Number(v)) },
    xAxis: { ...(chartBase.xAxis as object), type: "value", axisLabel: { formatter: usd } },
    yAxis: {
      ...(chartBase.yAxis as object),
      type: "category",
      data: sorted.map((r) => r.service.replace("Amazon ", "")),
      axisLabel: { color: "#A5B1C5", fontSize: 11, width: 150, overflow: "truncate" },
    },
    series: [
      {
        name: "Monthly spend",
        type: "bar",
        itemStyle: { color: CHART_PALETTE[0], borderRadius: [0, 3, 3, 0] },
        barWidth: 12,
        data: sorted.map((r) => r.amount),
      },
    ],
  };
}

export function opportunitiesByCategoryOption(rows: OpportunityCategory[]): EChartsOption {
  return {
    ...chartBase,
    tooltip: { ...chartBase.tooltip, valueFormatter: (v) => usd(Number(v)) },
    legend: { ...(chartBase.legend as object), bottom: 0 },
    xAxis: { ...(chartBase.xAxis as object), type: "category", data: rows.map((r) => r.category) },
    yAxis: { ...(chartBase.yAxis as object), type: "value", axisLabel: { formatter: usd } },
    series: [
      {
        name: "Est. monthly savings",
        type: "bar",
        itemStyle: { color: CHART_PALETTE[2], borderRadius: [3, 3, 0, 0] },
        barWidth: 28,
        data: rows.map((r) => r.monthlySavings),
      },
    ],
  };
}

export function topDriversOption(
  rows: { name: string; monthlyCost: number }[],
): EChartsOption {
  return {
    ...chartBase,
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    tooltip: { ...chartBase.tooltip, valueFormatter: (v) => usd(Number(v)) },
    xAxis: { ...(chartBase.xAxis as object), type: "value", axisLabel: { formatter: usd } },
    yAxis: {
      ...(chartBase.yAxis as object),
      type: "category",
      data: rows.map((r) => r.name),
      axisLabel: { color: "#A5B1C5", fontSize: 11 },
    },
    series: [
      {
        name: "Monthly cost",
        type: "bar",
        itemStyle: { color: CHART_PALETTE[1], borderRadius: [0, 3, 3, 0] },
        barWidth: 12,
        data: rows.map((r) => r.monthlyCost),
      },
    ],
  };
}

export function spendComparisonOption(current: CostPoint[], previous: CostPoint[]): EChartsOption {
  return {
    ...chartBase,
    tooltip: { ...chartBase.tooltip, valueFormatter: (v) => usd(Number(v)) },
    legend: { ...(chartBase.legend as object), top: 0, right: 0 },
    grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
    xAxis: { ...(chartBase.xAxis as object), type: "category", data: current.map((p) => p.date) },
    yAxis: { ...(chartBase.yAxis as object), type: "value", axisLabel: { formatter: usd } },
    series: [
      {
        name: "Current period",
        type: "line",
        smooth: true,
        showSymbol: false,
        lineStyle: { color: CHART_PALETTE[0], width: 2 },
        data: current.map((p) => p.amount),
      },
      {
        name: "Previous period",
        type: "line",
        smooth: true,
        showSymbol: false,
        lineStyle: { color: CHART_PALETTE[5], width: 2, type: "dashed" },
        data: previous.map((p) => p.amount),
      },
    ],
  };
}