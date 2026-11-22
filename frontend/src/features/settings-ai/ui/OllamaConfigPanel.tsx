import {
  getOllamaPullStatus,
  getOllamaSettings,
  listOllamaModels,
  patchOllamaSettings,
  pullOllamaModel,
  testOllamaConnection,
  type OllamaModelsResponse,
  type OllamaPullProgress,
  type OllamaSettings,
} from "@/features/settings-ai/api/settings-ai.api.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { Button } from "@/shared/components/Button/Button.tsx";
import { toError } from "@/shared/lib/errors.ts";
import { Cpu, Download, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export function OllamaConfigPanel({
  authClient,
  onNotice,
  onError,
}: {
  authClient: MaybeClient;
  onNotice: (msg: string | null) => void;
  onError: (msg: string | null) => void;
}) {
  const [settings, setSettings] = useState<OllamaSettings | null>(null);
  const [modelsData, setModelsData] = useState<OllamaModelsResponse | null>(
    null,
  );
  const [downloads, setDownloads] = useState<OllamaPullProgress[]>([]);
  const [baseUrl, setBaseUrl] = useState("http://ollama:11434");
  const [model, setModel] = useState("llama3.2:3b");
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [cfg, models, pullStatus] = await Promise.all([
        getOllamaSettings(authClient),
        listOllamaModels(authClient),
        getOllamaPullStatus(authClient),
      ]);
      setSettings(cfg);
      setBaseUrl(cfg.base_url);
      setModel(cfg.model);
      setModelsData(models);
      setDownloads(pullStatus.downloads || []);
    } catch (caught) {
      onError(toError(caught).message);
    }
  }, [authClient, onError]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    const hasActive = downloads.some((d) => d.status === "downloading");
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void getOllamaPullStatus(authClient)
        .then((res) => setDownloads(res.downloads || []))
        .catch(() => {});
    }, 2500);
    return () => window.clearInterval(timer);
  }, [authClient, downloads]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    onError(null);
    onNotice(null);
    try {
      const updated = await patchOllamaSettings(authClient, {
        base_url: baseUrl.trim(),
        model: model.trim(),
      });
      setSettings(updated);
      onNotice("Configuración de Ollama local guardada.");
    } catch (caught) {
      onError(toError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePull(modelId: string) {
    setBusy(true);
    onError(null);
    onNotice(null);
    try {
      const progress = await pullOllamaModel(authClient, modelId);
      setDownloads((prev) => [
        progress,
        ...prev.filter((item) => item.model !== modelId),
      ]);
      onNotice(`Descarga iniciada para ${modelId}.`);
    } catch (caught) {
      onError(toError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    setBusy(true);
    onError(null);
    onNotice(null);
    try {
      const res = await testOllamaConnection(authClient, model.trim());
      if (res.result === "ok") {
        onNotice(`Conexión con Ollama local verificada (${res.model}).`);
      } else {
        onError(res.reason || `Error en prueba de Ollama (${res.result}).`);
      }
      await loadAll();
    } catch (caught) {
      onError(toError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  const installedNames = new Set(
    (modelsData?.installed || []).map((item) => item.name),
  );

  return (
    <div className="settings-ai-grid">
      <section className="settings-ai-card">
        <div className="settings-ai-card-title">
          <Cpu size={18} aria-hidden="true" />
          <h2>Ollama local (sin API key comercial)</h2>
        </div>
        <p className="settings-ai-meta">
          Estado del servidor:{" "}
          <strong>
            {modelsData?.reachable ? "Conectado" : "No accesible"}
          </strong>
          {modelsData?.reason ? ` — ${modelsData.reason}` : ""}
        </p>
        <form className="settings-ai-form" onSubmit={handleSave}>
          <label>
            Endpoint local autorizado
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>
          <label>
            Modelo activo
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </label>
          <div className="settings-ai-actions">
            <Button type="submit" variant="primary" disabled={busy}>
              Guardar Ollama
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={handleTest}
            >
              <ShieldCheck size={14} aria-hidden="true" /> Probar consulta
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => void loadAll()}
            >
              <RefreshCw size={14} aria-hidden="true" /> Actualizar lista
            </Button>
          </div>
        </form>
        {settings?.last_check && (
          <p className="settings-ai-meta">
            Última prueba: <strong>{settings.last_check.result}</strong>
            {settings.last_check.reason
              ? ` (${settings.last_check.reason})`
              : ""}
          </p>
        )}
      </section>

      <section className="settings-ai-card">
        <div className="settings-ai-card-title">
          <Download size={18} aria-hidden="true" />
          <h2>Catálogo CPU autorizado</h2>
        </div>
        <p className="settings-ai-meta">
          No se descargan modelos automáticamente al iniciar. Elige un modelo
          compatible con tu RAM y almacenamiento.
        </p>
        <div className="ui-stack-md">
          {(modelsData?.catalog || []).map((item) => {
            const installed = installedNames.has(item.id);
            const activeDl = downloads.find((d) => d.model === item.id);
            return (
              <div key={item.id} className="ui-subcard ui-subcard--row">
                <div>
                  <strong>{item.label}</strong> <code>{item.id}</code>
                  <div className="settings-ai-meta">
                    Tamaño ~{item.size_gb} GB · RAM mínima {item.min_ram_gb} GB
                    — {item.description}
                  </div>
                  {activeDl && (
                    <div className="settings-ai-meta">
                      Estado: <strong>{activeDl.status}</strong> (
                      {activeDl.percent}%) — {activeDl.detail}
                    </div>
                  )}
                </div>
                <div className="ui-toolbar-row">
                  {installed ? (
                    <Button
                      type="button"
                      variant="primary"
                      onClick={() => setModel(item.id)}
                    >
                      Usar modelo
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={busy || activeDl?.status === "downloading"}
                      onClick={() => void handlePull(item.id)}
                    >
                      Descargar
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
