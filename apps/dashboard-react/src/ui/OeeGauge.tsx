import type React from "react";

import type { OeeReading } from "@/contexts/monitoring";

type OeeFactor = "oee" | "availability" | "performance" | "quality";

const FACTORS: { key: OeeFactor; label: string }[] = [
  { key: "oee", label: "OEE" },
  { key: "availability", label: "Availability" },
  { key: "performance", label: "Performance" },
  { key: "quality", label: "Quality" },
];

function toPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** Renders the OEE reading and its A·P·Q factors as a row of cards. Pure presentation. */
export function OeeGauge({ reading }: { reading: OeeReading }): React.JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="oee-gauge">
      {FACTORS.map(({ key, label }) => (
        <div key={key} className="rounded-2xl bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
          <div className="mt-1 text-2xl font-bold text-slate-900" data-testid={`oee-${key}`}>
            {toPercent(reading[key])}
          </div>
        </div>
      ))}
    </div>
  );
}
