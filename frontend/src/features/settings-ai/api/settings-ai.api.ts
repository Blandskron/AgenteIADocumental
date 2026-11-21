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

