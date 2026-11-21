import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";

export interface StudioTemplateList {
  templates: string[];
}

export interface StudioValidateResponse {
  valid: boolean;
  score: number;
  total_claims: number;
  anchored_claims: number;
  errors: string[];
}

export interface StudioConceptGraph {
  nodes: Array<{ id: string; label: string }>;
  edges: Array<{ source: string; target: string }>;
}

export interface StudioChartPoint {
  label: string;
  value: number;
  provenance: string;
}

export function listStudioTemplates(studioClient: MaybeClient) {
  return requireClient(studioClient)<StudioTemplateList>(
    "/api/v1/studio/templates",
    { method: "GET" },
  );
}

export function validateStudioMermaid(
  studioClient: MaybeClient,
  source: string,
) {
  return requireClient(studioClient)<{ status: string; source: string }>(
    "/api/v1/studio/mermaid/validate",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    },
  );
}

export function exportStudioCsv(
  studioClient: MaybeClient,
  artifact: Record<string, unknown>,
) {
  return requireClient(studioClient)<{ csv: string }>(
    "/api/v1/studio/export-csv",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(artifact),
    },
  );
}
