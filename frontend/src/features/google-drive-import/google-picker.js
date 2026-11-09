function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    const timer = setTimeout(() => { script.remove(); reject(new Error("Google Picker tardó demasiado en cargar.")); }, 15000);
    script.onload = () => { clearTimeout(timer); resolve(); };
    script.onerror = () => {
      clearTimeout(timer);
      script.remove();
      reject(new Error("No se pudo cargar el selector de Google Drive."));
    };
    document.head.append(script);
  });
}

let pickerLibraries;

function loadPickerLibraries() {
  pickerLibraries ??= Promise.all([
    window.gapi || loadScript("https://apis.google.com/js/api.js"),
    window.google?.accounts?.oauth2 || loadScript("https://accounts.google.com/gsi/client"),
  ]).then(() => new Promise((resolve, reject) => {
    window.gapi.load("picker", {
      callback: resolve,
      onerror: () => reject(new Error("No se pudo iniciar Google Picker.")),
      timeout: 10000,
      ontimeout: () => reject(new Error("Google Picker tardó demasiado en cargar.")),
    });
  })).catch((error) => {
    pickerLibraries = undefined;
    throw error;
  });
  return pickerLibraries;
}

export async function openGoogleDrivePicker({ appId, clientId, developerKey, connection, signal }) {
  if (!appId || !clientId || !developerKey) {
    throw new Error("Falta configurar Google Picker.");
  }

  if (!connection?.enabled || !connection?.connected || connection.busy || connection.oauthClientId !== clientId || connection.pickerAppId !== appId || !connection.providerAccountId) {
    throw new Error("Picker debe usar la aplicación y cuenta de la conexión activa de Drive.");
  }
  await bounded((resolve, reject) => loadPickerLibraries().then(resolve, reject), signal, 20000);
  signal?.throwIfAborted();
  const { picker, accounts } = window.google;
  const token = await bounded((resolve, reject) => {
    const fail = () => reject(new Error("No se pudo autorizar el acceso a Google Drive."));
    accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: "https://www.googleapis.com/auth/drive.file",
      callback: (response) => typeof response.access_token === "string" && /^[A-Za-z0-9._~+\/-]{1,8192}$/.test(response.access_token) ? resolve(response.access_token) : fail(),
      error_callback: fail,
    }).requestAccessToken();
  }, signal, 60000);
  signal?.throwIfAborted();

  const identity = await fetch("https://www.googleapis.com/drive/v3/about?fields=user(permissionId)", { headers: { Authorization: `Bearer ${token}` }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000), cache: "no-store", credentials: "omit" });
  if (!identity.ok || (await identity.json()).user?.permissionId !== connection.providerAccountId) {
    throw new Error("Selecciona la misma cuenta Google que conectaste a la plataforma.");
  }

  signal?.throwIfAborted();
  let instance;
  return bounded((resolve, reject) => {
    const view = new picker.DocsView(picker.ViewId.DOCS).setMode(picker.DocsViewMode.LIST);
    instance = new picker.PickerBuilder()
      .setMaxItems(25)
      .setAppId(appId)
      .setDeveloperKey(developerKey)
      .setOAuthToken(token)
      .addView(view)
      .enableFeature(picker.Feature.MULTISELECT_ENABLED)
      .setCallback((response) => {
        const action = response[picker.Response.ACTION];
        if (action === picker.Action.CANCEL) resolve([]);
        if (action === picker.Action.PICKED) {
          const files = response[picker.Response.DOCUMENTS];
          if (!Array.isArray(files) || files.length > 25 || files.some((file) => !/^[A-Za-z0-9_-]{1,128}$/.test(file[picker.Document.ID] || ""))) { reject(new Error("Selecciona hasta 25 archivos con IDs válidos.")); return; }
          resolve(files.map((file) => ({
            fileId: file[picker.Document.ID],
            name: file[picker.Document.NAME],
            mimeType: file[picker.Document.MIME_TYPE],
          })));
        }
      })
      .build();
    instance.setVisible(true);
  }, signal, 300000, () => instance?.dispose());
}

// Always remove timers/listeners; late GIS/Picker callbacks cannot settle a canceled operation.
function bounded(start, signal, milliseconds, cleanup = () => {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      try { cleanup(); } finally { fn(value); }
    };
    const abort = () => finish(reject, new DOMException("Operación cancelada.", "AbortError"));
    const timer = setTimeout(() => finish(reject, new Error("Google Drive tardó demasiado en responder.")), milliseconds);
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) { abort(); return; }
    try { start((value) => finish(resolve, value), (error) => finish(reject, error)); }
    catch (error) { finish(reject, error); }
  });
}
