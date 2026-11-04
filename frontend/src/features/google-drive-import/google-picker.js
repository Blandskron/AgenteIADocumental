function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => {
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

export async function openGoogleDrivePicker({ appId, clientId, developerKey }) {
  if (!appId || !clientId || !developerKey) {
    throw new Error("Falta configurar Google Picker.");
  }

  await loadPickerLibraries();
  const { picker, accounts } = window.google;
  const token = await new Promise((resolve, reject) => {
    const fail = () => reject(new Error("No se pudo autorizar el acceso a Google Drive."));
    accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: "https://www.googleapis.com/auth/drive.file",
      callback: (response) => response.access_token ? resolve(response.access_token) : fail(),
      error_callback: fail,
    }).requestAccessToken();
  });

  return new Promise((resolve) => {
    const view = new picker.DocsView(picker.ViewId.DOCS).setMode(picker.DocsViewMode.LIST);
    new picker.PickerBuilder()
      .setAppId(appId)
      .setDeveloperKey(developerKey)
      .setOAuthToken(token)
      .addView(view)
      .enableFeature(picker.Feature.MULTISELECT_ENABLED)
      .setCallback((response) => {
        const action = response[picker.Response.ACTION];
        if (action === picker.Action.CANCEL) resolve([]);
        if (action === picker.Action.PICKED) {
          resolve(response[picker.Response.DOCUMENTS].map((file) => ({
            fileId: file[picker.Document.ID],
            name: file[picker.Document.NAME],
            mimeType: file[picker.Document.MIME_TYPE],
          })));
        }
      })
      .build()
      .setVisible(true);
  });
}
