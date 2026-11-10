interface SpeechResult {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}
interface BrowserSpeechRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResult) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  abort(): void;
}
interface PickerInstance {
  setVisible(visible: boolean): void;
  dispose(): void;
}
interface PickerBuilder {
  setMaxItems(count: number): this;
  setAppId(id: string): this;
  setDeveloperKey(key: string): this;
  setOAuthToken(token: string): this;
  addView(view: unknown): this;
  enableFeature(feature: string): this;
  setCallback(callback: (response: Record<string, unknown>) => void): this;
  build(): PickerInstance;
}
interface Window {
  SpeechRecognition?: new () => BrowserSpeechRecognition;
  webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
  gapi?: {
    load(
      name: string,
      options: {
        callback: () => void;
        onerror: () => void;
        timeout: number;
        ontimeout: () => void;
      },
    ): void;
  };
  google?: {
    accounts: {
      oauth2: {
        initTokenClient(options: {
          client_id: string;
          scope: string;
          callback: (response: { access_token?: string }) => void;
          error_callback: () => void;
        }): { requestAccessToken(): void };
      };
    };
    picker: {
      DocsView: new (id: string) => { setMode(mode: string): unknown };
      PickerBuilder: new () => PickerBuilder;
      ViewId: { DOCS: string };
      DocsViewMode: { LIST: string };
      Feature: { MULTISELECT_ENABLED: string };
      Response: { ACTION: string; DOCUMENTS: string };
      Action: { CANCEL: string; PICKED: string };
      Document: { ID: string; NAME: string; MIME_TYPE: string };
    };
  };
}
