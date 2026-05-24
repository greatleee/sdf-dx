import { http, HttpResponse } from "msw";

/**
 * MSW handlers for `dev:fake` / `e2e:fake`: serve the read API with believable values so the
 * REAL HTTP adapter runs against a controlled backend. No WS feed in fake mode, so the
 * dashboard falls back to polling these endpoints. Shapes match the OpenAPI contract.
 */
export const handlers = [
  http.get("/api/v1/lines/:lineId/state", ({ params }) =>
    HttpResponse.json({
      lineId: String(params.lineId),
      state: "RUNNING",
      since: new Date().toISOString(),
    }),
  ),
  http.get("/api/v1/lines/:lineId/oee", ({ params, request }) => {
    const window = new URL(request.url).searchParams.get("window") ?? "5m";
    const availability = 0.92;
    const performance = 0.88;
    const quality = 0.99;
    return HttpResponse.json({
      lineId: String(params.lineId),
      window,
      availability,
      performance,
      quality,
      oee: availability * performance * quality,
      observedAt: new Date().toISOString(),
    });
  }),
];
