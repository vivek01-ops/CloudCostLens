"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ChartCard({
  title,
  description,
  option,
  height = 280,
  note,
}: {
  title: string;
  description?: string;
  option: EChartsOption;
  height?: number;
  note?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <ReactECharts
          option={option}
          style={{ height, width: "100%" }}
          opts={{ renderer: "canvas" }}
          notMerge
          lazyUpdate
        />
        {note ? <p className="mt-2 text-[11px] text-secondary">{note}</p> : null}
      </CardContent>
    </Card>
  );
}