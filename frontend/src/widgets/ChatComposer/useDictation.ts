import { useEffect, useRef, useState } from "react";
export function useDictation(onTranscript: (transcript: string) => void) {
  const recognition = useRef<BrowserSpeechRecognition | null>(null);
  const callback = useRef(onTranscript);
  callback.current = onTranscript;
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  useEffect(
    () => () => {
      recognition.current?.abort();
    },
    [],
  );
  function toggle() {
    if (!Speech) return;
    if (listening) {
      recognition.current?.abort();
      return;
    }
    const instance = recognition.current ?? new Speech();
    recognition.current = instance;
    instance.lang = "es-ES";
    instance.continuous = false;
    instance.interimResults = false;
    instance.onresult = (event) => {
      callback.current(event.results[0][0].transcript);
    };
    instance.onend = () => setListening(false);
    instance.onerror = () => {
      setError(
        "No se pudo dictar. Revisa el permiso del micrófono o escribe tu pregunta.",
      );
      setListening(false);
    };
    setError("");
    try {
      instance.start();
      setListening(true);
    } catch {
      setError("No se pudo iniciar el dictado. Inténtalo de nuevo.");
    }
  }
  return { supported: Boolean(Speech), listening, error, toggle };
}
