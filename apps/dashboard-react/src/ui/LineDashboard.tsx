import type React from "react";

import { useLineOee, useLineState, useSelectedLineId } from "@/contexts/monitoring";

import { LineStatePill } from "./LineStatePill";
import { OeeGauge } from "./OeeGauge";

/** Render data when present, else a transport-error message, else a loading placeholder (§6). */
function AsyncSlot<T>({
  data,
  isError,
  errorLabel,
  errorTestId,
  children,
}: {
  data: T | undefined;
  isError: boolean;
  errorLabel: string;
  errorTestId: string;
  children: (value: T) => React.JSX.Element;
}): React.JSX.Element {
  if (data !== undefined) return children(data);
  if (isError) {
    return (
      <p className="text-sm text-rose-600" data-testid={errorTestId}>
        {errorLabel}
      </p>
    );
  }
  return <p className="text-slate-500">Loading…</p>;
}

/**
 * The Phase-1 dashboard for a single Line: live Line state (WS-fed, polling fallback) + OEE.
 * Pure view — it reads data through application hooks and renders; no IO, no business rules (§7).
 */
export function LineDashboard(): React.JSX.Element {
  const lineId = useSelectedLineId();
  const { snapshot, isError: stateError, live } = useLineState(lineId);
  const { reading, isError: oeeError } = useLineOee(lineId, "5m");

  return (
    <section className="space-y-6" data-testid="line-dashboard">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">Line state</span>
          {!live && (
            <span
              className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
              data-testid="line-state-polling"
            >
              polling (reconnecting)
            </span>
          )}
        </div>
        <AsyncSlot
          data={snapshot}
          isError={stateError}
          errorLabel="Line state unavailable"
          errorTestId="line-state-error"
        >
          {(snap) => <LineStatePill snapshot={snap} />}
        </AsyncSlot>
      </div>

      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">OEE — last 5 minutes</div>
        <AsyncSlot
          data={reading}
          isError={oeeError}
          errorLabel="OEE unavailable"
          errorTestId="oee-error"
        >
          {(value) => <OeeGauge reading={value} />}
        </AsyncSlot>
      </div>
    </section>
  );
}
