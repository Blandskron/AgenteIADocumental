import { FileText, Mic, Plus, Send, Square, Trash2 } from "lucide-react";
import type { ChangeEvent, KeyboardEvent, RefObject } from "react";
import { useDictation } from "./useDictation.ts";
interface ComposerProps {
  fileInputRef: RefObject<HTMLInputElement | null>;
  isBusy: boolean;
  onClearFile: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onOpenFilePicker: () => void;
  onQuestionChange: (question: string) => void;
  onSubmit: () => void;
  onUploadOnly: () => void;
  question: string;
  selectedFile: File | null;
  isStarterState?: boolean;
  onDictate: (transcript: string) => void;
}
export function ChatComposer({
  fileInputRef,
  isBusy,
  onClearFile,
  onFileChange,
  onOpenFilePicker,
  onQuestionChange,
  onSubmit,
  onUploadOnly,
  question,
  selectedFile,
  isStarterState = false,
  onDictate,
}: ComposerProps) {
  const dictation = useDictation(onDictate);
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      onSubmit();
    }
  }
  return (
    <footer className={`composer ${isStarterState ? "starter-composer" : ""}`}>
      {selectedFile && (
        <div className="attachment-bar">
          <FileText size={16} aria-hidden="true" />
          <span>{selectedFile.name}</span>
          <button
            type="button"
            className="mini-action"
            onClick={onUploadOnly}
            disabled={isBusy}
          >
            Procesar
          </button>
          <button
            type="button"
            onClick={onClearFile}
            disabled={isBusy}
            aria-label="Quitar archivo"
          >
            <Trash2 size={15} />
          </button>
        </div>
      )}
      <div className="composer-box">
        <button
          className="attach-button"
          type="button"
          onClick={onOpenFilePicker}
          disabled={isBusy}
          aria-label="Adjuntar documento"
        >
          <Plus size={20} />
        </button>
        <textarea
          aria-label="Pregunta documental"
          aria-describedby="composer-help"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedFile
              ? "Pregunta sobre el documento adjunto…"
              : "Pregunta sobre tus documentos…"
          }
        />
        {dictation.supported && (
          <button
            className="mic-button"
            type="button"
            aria-label={
              dictation.listening ? "Detener dictado" : "Dictar por voz"
            }
            aria-pressed={dictation.listening}
            disabled={isBusy}
            onClick={dictation.toggle}
          >
            {dictation.listening ? <Square size={17} /> : <Mic size={19} />}
          </button>
        )}
        <button
          className="send-button"
          type="button"
          onClick={onSubmit}
          disabled={isBusy || !question.trim()}
          aria-label="Enviar pregunta"
        >
          <Send size={18} />
        </button>
      </div>
      <p className="composer-help" id="composer-help">
        Enter para enviar · Mayús + Enter para una nueva línea. Comprueba las
        fuentes de cada respuesta.
      </p>
      {dictation.error && (
        <p role="alert" className="composer-help">
          {dictation.error}
        </p>
      )}
      <input
        ref={fileInputRef}
        className="hidden-file"
        aria-label="Archivo adjunto"
        type="file"
        onChange={onFileChange}
      />
    </footer>
  );
}
