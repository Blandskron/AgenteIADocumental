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

export async function listStudioTemplates(
  studioClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
): Promise<StudioTemplateList> {
  const raw = await requireClient(studioClient)<StudioTemplateList>(
    "/api/v1/studio/templates",
    { method: "GET", ...(signal ? { signal } : {}) },
  );
  return {
    templates: Array.isArray(raw?.templates) ? raw.templates : [],
  };
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

export interface StudioArtifactRecord {
  artifact_id: string;
  collection_id: string;
  template_id: string;
  title: string;
  status: string;
  version: number;
  groundedness_score: number;
  content: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface StudioJobRecord {
  job_id: string;
  collection_id: string;
  template_id: string;
  status: string;
  step: string;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string;
}

export async function listStudioArtifacts(
  studioClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
): Promise<{ items: StudioArtifactRecord[] }> {
  const raw = await requireClient(studioClient)<{
    items: StudioArtifactRecord[];
  }>("/api/v1/studio/artifacts", {
    method: "GET",
    ...(signal ? { signal } : {}),
  });
  return {
    items: Array.isArray(raw?.items) ? raw.items : [],
  };
}

export function createStudioArtifact(
  studioClient: MaybeClient,
  payload: {
    template_id: string;
    title: string;
    document_ids: string[];
    content: Record<string, unknown>;
  },
) {
  return requireClient(studioClient)<StudioArtifactRecord>(
    "/api/v1/studio/artifacts",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function listStudioJobs(
  studioClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
): Promise<{ items: StudioJobRecord[] }> {
  const raw = await requireClient(studioClient)<{ items: StudioJobRecord[] }>(
    "/api/v1/studio/jobs",
    { method: "GET", ...(signal ? { signal } : {}) },
  );
  return {
    items: Array.isArray(raw?.items) ? raw.items : [],
  };
}

export function cancelStudioJob(studioClient: MaybeClient, jobId: string) {
  return requireClient(studioClient)<{ job_id: string; cancelled: boolean }>(
    `/api/v1/studio/jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: "POST" },
  );
}
