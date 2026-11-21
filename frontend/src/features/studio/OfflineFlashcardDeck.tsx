import { useState } from "react";

export interface LocalFlashcard {
  id: string;
  front: string;
  back: string;
  repetitions: number;
  intervalDays: number;
  easeFactor: number;
}

export function applySm2Offline(
  card: LocalFlashcard,
  quality: number,
): LocalFlashcard {
  const q = Math.max(0, Math.min(5, Math.round(quality)));
  if (q < 3) {
    return { ...card, repetitions: 0, intervalDays: 1 };
  }
  const repetitions = card.repetitions + 1;
  const intervalDays =
    repetitions === 1
      ? 1
      : repetitions === 2
        ? 6
        : Math.max(1, Math.round(card.intervalDays * card.easeFactor));
  const easeFactor = Number(
    Math.max(
      1.3,
      card.easeFactor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)),
    ).toFixed(4),
  );
  return { ...card, repetitions, intervalDays, easeFactor };
}

const DEFAULT_CARDS: LocalFlashcard[] = [
  {
    id: "card-1",
    front:
      "¿Qué índice vectorial reemplaza a IVFFlat en Blandskron Documental?",
    back: "HNSW (vector_cosine_ops) sobre pgvector para mejorar recall y latencia desde el primer documento.",
    repetitions: 0,
    intervalDays: 1,
    easeFactor: 2.5,
  },
  {
    id: "card-2",
    front: "¿Afecta revocar la clave de Groq a los embeddings locales?",
    back: "No. multilingual-e5-small (384 dims) corre localmente en CPU sin red ni clave externa.",
    repetitions: 0,
    intervalDays: 1,
    easeFactor: 2.5,
  },
];

export function OfflineFlashcardDeck() {
  const [cards, setCards] = useState<LocalFlashcard[]>(DEFAULT_CARDS);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  const current = cards[index % cards.length];

  function rate(quality: number) {
    const updated = applySm2Offline(current, quality);
    setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setFlipped(false);
    setIndex((prev) => (prev + 1) % cards.length);
  }

  return (
    <section
      className="settings-ai-card"
      aria-labelledby="studio-flashcards-heading"
    >
      <h2 id="studio-flashcards-heading">Práctica offline (SM-2 sin Groq)</h2>
      <p className="settings-ai-meta">
        Repaso espaciado 100 % local en el navegador · Próximo intervalo:{" "}
        <strong>{current.intervalDays} día(s)</strong> · Repeticiones:{" "}
        <strong>{current.repetitions}</strong>
      </p>
      <div
        style={{
          padding: "1rem",
          borderRadius: "10px",
          border: "1px solid var(--border-subtle, #cbd5e1)",
        }}
      >
        <p style={{ margin: "0 0 0.5rem", fontWeight: 600 }}>{current.front}</p>
        {flipped && <p style={{ margin: 0 }}>{current.back}</p>}
      </div>
      <div className="settings-ai-actions">
        {!flipped ? (
          <button
            type="button"
            className="btn-primary"
            onClick={() => setFlipped(true)}
          >
            Mostrar respuesta
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn-danger"
              onClick={() => rate(1)}
            >
              Repetir (1d)
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => rate(3)}
            >
              Bien
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => rate(5)}
            >
              Fácil
            </button>
          </>
        )}
      </div>
    </section>
  );
}
