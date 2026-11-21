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

export function listStudioArtifacts(studioClient: MaybeClient) {
  return requireClient(studioClient)<{ items: StudioArtifactRecord[] }>(
    "/api/v1/studio/artifacts",
    { method: "GET" },
  );
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

export function listStudioJobs(studioClient: MaybeClient) {
  return requireClient(studioClient)<{ items: StudioJobRecord[] }>(
    "/api/v1/studio/jobs",
    { method: "GET" },
  );
}

export function cancelStudioJob(studioClient: MaybeClient, jobId: string) {
  return requireClient(studioClient)<{ job_id: string; cancelled: boolean }>(
    `/api/v1/studio/jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: "POST" },
  );
}
