import { useRef } from "react";
import { AudioLines, ChevronDown, FileText, Mic, Plus, Send, Trash2 } from "lucide-react";

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
}) {
  const recognitionRef = useRef(null);

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  function handleMicClick() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      alert("Tu navegador no soporta reconocimiento de voz.");
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!recognitionRef.current) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.lang = "es-ES";
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (onDictate) onDictate(transcript);
      };
    }
    recognitionRef.current.start();
  }

  return (
    <footer className={`composer ${isStarterState ? "starter-composer" : ""}`}>
      {selectedFile && (
        <div className="attachment-bar">
          <FileText size={16} />
          <span>{selectedFile.name}</span>
          <button className="mini-action" onClick={onUploadOnly} disabled={isBusy}>
            Procesar
          </button>
          <button onClick={onClearFile} aria-label="Quitar archivo">
            <Trash2 size={15} />
          </button>
        </div>
      )}

      <div className="composer-box">
        <button className="attach-button" type="button" onClick={onOpenFilePicker} aria-label="Adjuntar documento">
          <Plus size={20} />
        </button>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={selectedFile ? "Pregunta sobre el documento adjunto..." : "Pregunta lo que quieras"}
        />
        {isStarterState && (
          <button className="model-selector-button" type="button" aria-label="Modelo seleccionado">
            Instant <ChevronDown size={14} />
          </button>
        )}
        <button className="mic-button" type="button" aria-label="Dictar por voz" onClick={handleMicClick}>
          <Mic size={19} />
        </button>
        <button className="send-button" onClick={onSubmit} disabled={isBusy || !question.trim()} aria-label="Enviar pregunta">
          {question.trim() ? <Send size={18} /> : <AudioLines size={20} />}
        </button>
      </div>

      <input ref={fileInputRef} className="hidden-file" type="file" onChange={onFileChange} />
    </footer>
  );
}
