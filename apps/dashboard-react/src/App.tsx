import type React from "react";
import { LineDashboard } from "@/ui/LineDashboard";

export default function App(): React.JSX.Element {
  return (
    <main className="min-h-screen p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">SDF Manufacturing DX</h1>
        <p className="text-sm text-slate-600">Phase 1 — Single line vertical slice</p>
      </header>
      <LineDashboard />
    </main>
  );
}
