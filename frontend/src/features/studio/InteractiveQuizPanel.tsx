import { useState } from "react";

export interface DeterministicQuizItem {
  id: string;
  prompt: string;
  options: string[];
  correctIndex: number;
  explanation: string;
  citationLabel: string;
}

const SAMPLE_QUIZ: DeterministicQuizItem[] = [
  {
    id: "q-1",
    prompt:
      "¿Qué técnica combina búsqueda vectorial y Full-Text Search en el motor RAG?",
    options: [
      "Solo ILIKE sobre texto plano",
      "Reciprocal Rank Fusion (RRF)",
      "Reemplazo de embeddings locales por API externa",
    ],
    correctIndex: 1,
    explanation:
      "RRF fusiona los rankings de pgvector HNSW y ts_rank_cd sin requerir reentrenamiento.",
    citationLabel: "vector_repository_pgvector.py · R2-03",
  },
  {
    id: "q-2",
    prompt:
      "¿Cómo se almacenan las credenciales de Groq configuradas desde la web?",
    options: [
      "En localStorage del navegador",
      "En texto plano en PostgreSQL",
      "Cifradas con Fernet (secrets1.) en tenant_integrations",
    ],
    correctIndex: 2,
    explanation:
      "SecretsCipher cifra con Fernet autenticado y llave maestra fuera de la BD.",
    citationLabel: "secrets_cipher.py · R1-02",
  },
];

export function InteractiveQuizPanel() {
  const [selected, setSelected] = useState<Record<string, number>>({});

  return (
    <section className="settings-ai-card" aria-labelledby="studio-quiz-heading">
      <h2 id="studio-quiz-heading">Quiz verificado con citas (offline)</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {SAMPLE_QUIZ.map((item) => {
          const picked = selected[item.id];
          const answered = picked !== undefined;
          const correct = picked === item.correctIndex;
          return (
            <fieldset
              key={item.id}
              style={{
                border: "1px solid var(--border-subtle, #cbd5e1)",
                borderRadius: "10px",
                padding: "0.85rem",
                margin: 0,
              }}
            >
              <legend style={{ fontWeight: 600, padding: "0 0.35rem" }}>
                {item.prompt}
              </legend>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.4rem",
                }}
              >
                {item.options.map((opt, idx) => (
                  <label
                    key={opt}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="radio"
                      name={item.id}
                      checked={picked === idx}
                      onChange={() =>
                        setSelected((prev) => ({ ...prev, [item.id]: idx }))
                      }
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>
              {answered && (
                <p
                  role="status"
                  style={{
                    margin: "0.6rem 0 0",
                    fontSize: "0.86rem",
                    color: correct ? "#15803d" : "#b91c1c",
                  }}
                >
                  <strong>{correct ? "Correcto." : "Incorrecto."}</strong>{" "}
                  {item.explanation} (<code>{item.citationLabel}</code>)
                </p>
              )}
            </fieldset>
          );
        })}
      </div>
    </section>
  );
}
