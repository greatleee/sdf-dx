import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient();

async function bootstrap(): Promise<void> {
  if (import.meta.env.VITE_FAKE === "1") {
    const { worker } = await import("./testing/msw/browser");
    await worker.start({ onUnhandledRequest: "warn" });
  }
  const root = document.getElementById("root");
  if (root === null) throw new Error("Root element #root not found in DOM");
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

void bootstrap();
