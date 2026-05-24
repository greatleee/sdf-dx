import type React from "react";

import type { LineState, LineStateSnapshot } from "@/contexts/monitoring";

const STATE_STYLES: Record<LineState, { dot: string; label: string }> = {
  RUNNING: { dot: "bg-emerald-500", label: "text-emerald-700" },
  IDLE: { dot: "bg-slate-400", label: "text-slate-600" },
  DOWN: { dot: "bg-rose-500", label: "text-rose-700" },
  CHANGEOVER: { dot: "bg-amber-500", label: "text-amber-700" },
};

/** Renders the current Line state as a coloured pill. Pure presentation. */
export function LineStatePill({ snapshot }: { snapshot: LineStateSnapshot }): React.JSX.Element {
  const style = STATE_STYLES[snapshot.state];
  return (
    <div className="flex items-center gap-3" data-testid="line-state-pill">
      <span className={`inline-block size-3 rounded-full ${style.dot}`} aria-hidden="true" />
      <span className={`font-semibold ${style.label}`} data-testid="line-state-value">
        {snapshot.state}
      </span>
      <span className="text-xs text-slate-500">
        since {new Date(snapshot.since).toLocaleTimeString()}
      </span>
    </div>
  );
}
