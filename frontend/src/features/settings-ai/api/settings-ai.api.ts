import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";

export interface GroqParams {
  max_tokens: number;
  temperature: number;
  timeout_seconds: number;
}

export interface GroqLastCheck {
  at?: string | null;
  result: string;
  reason?: string | null;
}

export interface GroqSettings {
  provider: string;
  configured: boolean;
  status: "not_configured" | "ready_to_test" | "connected" | "error" | string;
  model: string;
  params: GroqParams;
  last_check: GroqLastCheck | null;
  key_fingerprint: string | null;
  encryption_ready: boolean;
  updated_at: string | null;
}

export interface GroqModelsResponse {
  result: string;
  models: string[];
  reason?: string | null;
}

export interface GroqTestResponse {
  result: string;
  model: string;
  models?: string[];
  reason?: string | null;
  checked_at: string;
}

export function getGroqSettings(authClient: MaybeClient) {
  return requireClient(authClient)<GroqSettings>("/api/integrations/groq/", {
    method: "GET",
  });
}

export function patchGroqSettings(
  authClient: MaybeClient,
  payload: { model?: string; params?: Partial<GroqParams> },
) {
  return requireClient(authClient)<GroqSettings>("/api/integrations/groq/", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function putGroqCredentials(authClient: MaybeClient, apiKey: string) {
  return requireClient(authClient)<GroqSettings>(
    "/api/integrations/groq/credentials/",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    },
  );
}

export function deleteGroqCredentials(authClient: MaybeClient) {
  return requireClient(authClient)<GroqSettings>(
    "/api/integrations/groq/credentials/",
    {
      method: "DELETE",
    },
  );
}

export function listGroqModels(authClient: MaybeClient) {
  return requireClient(authClient)<GroqModelsResponse>(
    "/api/integrations/groq/models/",
    {
      method: "GET",
    },
  );
}

export function testGroqConnection(authClient: MaybeClient, model?: string) {
  return requireClient(authClient)<GroqTestResponse>(
    "/api/integrations/groq/test/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(model ? { model } : {}),
    },
  );
}

export interface ActiveProviderState {
  active_provider: "groq" | "ollama";
  available_providers: Array<"groq" | "ollama">;
}

export interface OllamaSettings {
  provider: string;
  enabled: boolean;
  base_url: string;
  model: string;
  params: GroqParams;
  last_check: GroqLastCheck | null;
  updated_at: string | null;
}

export interface OllamaCatalogModel {
  id: string;
  label: string;
  size_gb: number;
  min_ram_gb: number;
  description: string;
}

export interface OllamaInstalledModel {
  name: string;
  size_bytes: number;
  modified_at?: string | null;
}

export interface OllamaModelsResponse {
  reachable: boolean;
  installed: OllamaInstalledModel[];
  catalog: OllamaCatalogModel[];
  reason?: string | null;
}

export interface OllamaPullProgress {
  model: string;
  status: "downloading" | "completed" | "error" | string;
  percent: number;
  completed_bytes: number;
  total_bytes: number;
  detail: string;
  updated_at: string;
}

export function getActiveAIProvider(authClient: MaybeClient) {
  return requireClient(authClient)<ActiveProviderState>(
    "/api/integrations/ai/provider/",
    { method: "GET" },
  );
}

export function setActiveAIProvider(
  authClient: MaybeClient,
  activeProvider: "groq" | "ollama",
) {
  return requireClient(authClient)<ActiveProviderState>(
    "/api/integrations/ai/provider/",
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_provider: activeProvider }),
    },
  );
}

export function getOllamaSettings(authClient: MaybeClient) {
  return requireClient(authClient)<OllamaSettings>(
    "/api/integrations/ollama/",
    { method: "GET" },
  );
}

export function patchOllamaSettings(
  authClient: MaybeClient,
  payload: { base_url?: string; model?: string; params?: Partial<GroqParams> },
) {
  return requireClient(authClient)<OllamaSettings>(
    "/api/integrations/ollama/",
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function listOllamaModels(authClient: MaybeClient) {
  return requireClient(authClient)<OllamaModelsResponse>(
    "/api/integrations/ollama/models/",
    { method: "GET" },
  );
}

export function pullOllamaModel(authClient: MaybeClient, model: string) {
  return requireClient(authClient)<OllamaPullProgress>(
    "/api/integrations/ollama/pull/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    },
  );
}

export function getOllamaPullStatus(authClient: MaybeClient) {
  return requireClient(authClient)<{ downloads: OllamaPullProgress[] }>(
    "/api/integrations/ollama/pull/status/",
    { method: "GET" },
  );
}

export function testOllamaConnection(authClient: MaybeClient, model?: string) {
  return requireClient(authClient)<GroqTestResponse>(
    "/api/integrations/ollama/test/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(model ? { model } : {}),
    },
  );
}
