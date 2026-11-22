import type { PageProps } from "@/app/router/useAppRouter.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import {
  deleteGroqCredentials,
  getActiveAIProvider,
  getGroqSettings,
  listGroqModels,
  patchGroqSettings,
  putGroqCredentials,
  setActiveAIProvider,
  testGroqConnection,
  type GroqSettings,
} from "@/features/settings-ai/api/settings-ai.api.ts";
import { OllamaConfigPanel } from "@/features/settings-ai/ui/OllamaConfigPanel.tsx";
import { Button } from "@/shared/components/Button/Button.tsx";
import { PageState } from "@/shared/components/PageState.tsx";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { toError } from "@/shared/lib/errors.ts";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";
import { Cpu, KeyRound, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import "./SettingsAIPage.css";

const STATUS_LABELS: Record<string, string> = {
  not_configured: "No configurado",
  ready_to_test: "Listo para probar",
  connected: "Conectado",
  error: "Con error",
};

export function SettingsAIPage({ onNavigate }: PageProps) {
  const { authClient, currentUser, logout } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [settings, setSettings] = useState<GroqSettings | null>(null);
  const [activeProvider, setActiveProvider] = useState<"groq" | "ollama">(
    "groq",
  );
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [apiKeyInput, setApiKeyInput] = useState("");
  const [modelInput, setModelInput] = useState("llama-3.3-70b-versatile");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [maxTokens, setMaxTokens] = useState(2000);
  const [temperature, setTemperature] = useState(0.3);
  const [timeoutSeconds, setTimeoutSeconds] = useState(60);

  const applySettings = useCallback((data: GroqSettings) => {
    setSettings(data);
    setModelInput(data.model || "llama-3.3-70b-versatile");
    setMaxTokens(data.params?.max_tokens ?? 2000);
    setTemperature(data.params?.temperature ?? 0.3);
    setTimeoutSeconds(data.params?.timeout_seconds ?? 60);
  }, []);

  const loadSettings = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [data, providerState] = await Promise.all([
          getGroqSettings(authClient, { signal }),
          getActiveAIProvider(authClient, { signal }).catch(() => ({
            active_provider: "groq" as const,
            available_providers: ["groq", "ollama"] as Array<"groq" | "ollama">,
          })),
        ]);
        if (signal?.aborted) return;
        applySettings(data);
        setActiveProvider(providerState.active_provider);
        if (data.configured) {
          try {
            const modelsResp = await listGroqModels(authClient, { signal });
            if (
              !signal?.aborted &&
              modelsResp.result === "ok" &&
              modelsResp.models.length > 0
            ) {
              setAvailableModels(modelsResp.models);
            }
          } catch {
            // Mantener input manual si el listado de modelos no responde.
          }
        }
      } catch (caught) {
        if (
          signal?.aborted ||
          (caught instanceof Error && caught.name === "AbortError")
        ) {
          return;
        }
        setError(
          toError(caught).message ||
            "No se pudo cargar la configuración de IA.",
        );
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [authClient, applySettings],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadSettings(controller.signal);
    return () => controller.abort();
  }, [loadSettings]);

  async function handleSaveCredentials(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      setError(
        "Ingresa una clave API de Groq o usa «Revocar clave» para eliminarla.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await putGroqCredentials(authClient, trimmed);
      setApiKeyInput("");
      applySettings(updated);
      setNotice(
        "Clave cifrada y guardada. Ejecuta «Probar conexión» para validar el modelo.",
      );
    } catch (caught) {
      setError(
        toError(caught).message || "No se pudo guardar la clave de Groq.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveParams(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await patchGroqSettings(authClient, {
        model: modelInput.trim(),
        params: {
          max_tokens: Number(maxTokens),
          temperature: Number(temperature),
          timeout_seconds: Number(timeoutSeconds),
        },
      });
      applySettings(updated);
      setNotice("Parámetros de generación actualizados.");
    } catch (caught) {
      setError(
        toError(caught).message || "No se pudieron actualizar los parámetros.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleTestConnection() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await testGroqConnection(
        authClient,
        modelInput.trim() || undefined,
      );
      if (result.models && result.models.length > 0) {
        setAvailableModels(result.models);
      }
      if (result.result === "ok") {
        setNotice(
          `Conexión verificada correctamente con el modelo ${result.model}.`,
        );
      } else {
        setError(
          result.reason || `La prueba devolvió estado: ${result.result}.`,
        );
      }
      const refreshed = await getGroqSettings(authClient);
      applySettings(refreshed);
    } catch (caught) {
      setError(
        toError(caught).message || "Error al probar la conexión con Groq.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await deleteGroqCredentials(authClient);
      setApiKeyInput("");
      setAvailableModels([]);
      applySettings(updated);
      setNotice(
        "Clave revocada. El chat volverá a .env o modo degradado; los embeddings locales siguen operativos.",
      );
    } catch (caught) {
      setError(toError(caught).message || "No se pudo revocar la clave.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          activeRoute={appRoutes.settingsAi}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onLogout={logout}
          onNavigate={onNavigate}
          user={currentUser}
        />
      }
    >
      <main
        id="main-content"
        tabIndex={-1}
        className="settings-ai-page blandskron-screen"
      >
        <header className="settings-ai-header">
          <div>
            <h1>Configuración de IA</h1>
            <p>
              Elige entre Groq en la nube u Ollama local sin editar archivos ni
              reiniciar servicios.
            </p>
          </div>
          <div className="ui-toolbar-row">
            <Button
              type="button"
              variant={activeProvider === "groq" ? "primary" : "secondary"}
              disabled={busy}
              onClick={() => {
                setBusy(true);
                setError(null);
                void setActiveAIProvider(authClient, "groq")
                  .then((res) => {
                    setActiveProvider(res.active_provider);
                    setNotice("Proveedor activo cambiado a Groq.");
                  })
                  .catch((caught) => setError(toError(caught).message))
                  .finally(() => setBusy(false));
              }}
            >
              Groq (Nube)
            </Button>
            <Button
              type="button"
              variant={activeProvider === "ollama" ? "primary" : "secondary"}
              disabled={busy}
              onClick={() => {
                setBusy(true);
                setError(null);
                void setActiveAIProvider(authClient, "ollama")
                  .then((res) => {
                    setActiveProvider(res.active_provider);
                    setNotice(
                      "Proveedor activo cambiado a Ollama local (sin envío a terceros).",
                    );
                  })
                  .catch((caught) => setError(toError(caught).message))
                  .finally(() => setBusy(false));
              }}
            >
              Ollama (Local)
            </Button>
            {settings && activeProvider === "groq" && (
              <span
                className={`settings-ai-badge status-${settings.status}`}
                role="status"
              >
                {STATUS_LABELS[settings.status] || settings.status}
              </span>
            )}
          </div>
        </header>

        {loading && <PageState title="Cargando configuración de IA…" loading />}

        {!loading && error && (
          <div
            className="settings-ai-alert settings-ai-alert-error"
            role="alert"
          >
            {error}
          </div>
        )}
        {!loading && notice && (
          <div className="settings-ai-alert settings-ai-alert-ok" role="status">
            {notice}
          </div>
        )}

        {!loading && activeProvider === "ollama" && (
          <OllamaConfigPanel
            authClient={authClient}
            onNotice={setNotice}
            onError={setError}
          />
        )}

        {!loading && activeProvider === "groq" && settings && (
          <div className="settings-ai-grid">
            <section
              className="settings-ai-card"
              aria-labelledby="groq-credentials-heading"
            >
              <div className="settings-ai-card-title">
                <KeyRound size={18} aria-hidden="true" />
                <h2 id="groq-credentials-heading">
                  Proveedor Groq (Generación)
                </h2>
              </div>

              {!settings.encryption_ready && (
                <p className="settings-ai-hint">
                  Define <code>SECRETS_ENCRYPTION_KEY</code> en el entorno del
                  servidor para habilitar el guardado cifrado.
                </p>
              )}

              <p className="settings-ai-meta">
                Huella actual:{" "}
                <strong>
                  {settings.key_fingerprint
                    ? `•••• ${settings.key_fingerprint}`
                    : "Sin clave guardada"}
                </strong>
                {settings.last_check?.at && (
                  <>
                    {" "}
                    · Última verificación:{" "}
                    <span>{settings.last_check.result}</span>
                  </>
                )}
              </p>

              <form
                onSubmit={handleSaveCredentials}
                className="settings-ai-form"
              >
                <label htmlFor="groq-api-key-input">Clave API de Groq</label>
                <input
                  id="groq-api-key-input"
                  type="password"
                  autoComplete="new-password"
                  autoCapitalize="off"
                  spellCheck={false}
                  placeholder={
                    settings.configured
                      ? "•••••••• (escribir para reemplazar)"
                      : "gsk_..."
                  }
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  disabled={busy}
                />
                <div className="settings-ai-actions">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={busy || !settings.encryption_ready}
                  >
                    Guardar clave
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleTestConnection}
                    disabled={busy || !settings.configured}
                  >
                    <RefreshCw size={15} aria-hidden="true" />
                    Probar conexión
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    onClick={handleRevoke}
                    disabled={busy || !settings.configured}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                    Revocar clave
                  </Button>
                </div>
              </form>
            </section>

            <section
              className="settings-ai-card"
              aria-labelledby="groq-model-heading"
            >
              <div className="settings-ai-card-title">
                <ShieldCheck size={18} aria-hidden="true" />
                <h2 id="groq-model-heading">Modelo y parámetros</h2>
              </div>

              <form onSubmit={handleSaveParams} className="settings-ai-form">
                <label htmlFor="groq-model-input">Modelo de chat</label>
                <input
                  id="groq-model-input"
                  list="groq-available-models"
                  value={modelInput}
                  onChange={(e) => setModelInput(e.target.value)}
                  disabled={busy}
                />
                <datalist id="groq-available-models">
                  {availableModels.map((modelId) => (
                    <option key={modelId} value={modelId} />
                  ))}
                </datalist>

                <details className="settings-ai-advanced">
                  <summary>Parámetros avanzados</summary>
                  <div className="settings-ai-advanced-fields">
                    <label htmlFor="groq-max-tokens">
                      Máximo de tokens
                      <input
                        id="groq-max-tokens"
                        type="number"
                        min={64}
                        max={8192}
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(Number(e.target.value))}
                        disabled={busy}
                      />
                    </label>
                    <label htmlFor="groq-temperature">
                      Temperatura
                      <input
                        id="groq-temperature"
                        type="number"
                        min={0}
                        max={1.5}
                        step={0.1}
                        value={temperature}
                        onChange={(e) => setTemperature(Number(e.target.value))}
                        disabled={busy}
                      />
                    </label>
                    <label htmlFor="groq-timeout">
                      Timeout (segundos)
                      <input
                        id="groq-timeout"
                        type="number"
                        min={5}
                        max={180}
                        value={timeoutSeconds}
                        onChange={(e) =>
                          setTimeoutSeconds(Number(e.target.value))
                        }
                        disabled={busy}
                      />
                    </label>
                  </div>
                </details>

                <div className="settings-ai-actions">
                  <Button type="submit" variant="primary" disabled={busy}>
                    Guardar parámetros
                  </Button>
                </div>
              </form>
            </section>

            <section
              className="settings-ai-card settings-ai-local-card"
              aria-labelledby="local-e5-heading"
            >
              <div className="settings-ai-card-title">
                <Cpu size={18} aria-hidden="true" />
                <h2 id="local-e5-heading">
                  Vectorización e indexación (local)
                </h2>
              </div>
              <p>
                Los embeddings se calculan localmente en CPU con{" "}
                <code>intfloat/multilingual-e5-small</code> (384 dimensiones,
                sin coste de API).
              </p>
              <p className="settings-ai-meta">
                Revocar o modificar la clave de Groq no interrumpe la carga,
                indexación, búsqueda ni biblioteca documental.
              </p>
            </section>
          </div>
        )}
      </main>
    </AppShell>
  );
}
