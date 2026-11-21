import { BarChart3, Network } from "lucide-react";
import type { VerifiedEvidenceRow } from "./studioExport.ts";

export interface ConceptNode {
  id: string;
  label: string;
}

export interface ConceptEdge {
  source: string;
  target: string;
}

const SAMPLE_NODES: ConceptNode[] = [
  { id: "n1", label: "Contrato Base" },
  { id: "n2", label: "Plazo (97 dias)" },
  { id: "n3", label: "Auditoria" },
];

const SAMPLE_EDGES: ConceptEdge[] = [
  { source: "n1", target: "n2" },
  { source: "n1", target: "n3" },
];

export const SAMPLE_VERIFIED_ROWS: VerifiedEvidenceRow[] = [
  {
    label: "Plazo contrato (dias)",
    value: 97,
    provenance: "doc-demo#0",
  },
  {
    label: "Cobertura citas (%)",
    value: 100,
    provenance: "studio-eval#0",
  },
];

export function VerifiedVisualsPanel({
  nodes = SAMPLE_NODES,
  edges = SAMPLE_EDGES,
  rows = SAMPLE_VERIFIED_ROWS,
}: {
  nodes?: ConceptNode[];
  edges?: ConceptEdge[];
  rows?: VerifiedEvidenceRow[];
}) {
  const maxVal = Math.max(1, ...rows.map((r) => Math.abs(r.value)));

  return (
    <section
      className="settings-ai-card"
      aria-labelledby="studio-visuals-heading"
    >
      <div className="settings-ai-card-title">
        <Network size={18} aria-hidden="true" />
        <h2 id="studio-visuals-heading">Visualizaciones deterministas</h2>
      </div>
      <p className="settings-ai-meta">
        Grafo conceptual derivado de <code>[[wikilinks]]</code> y gráfico
        generado exclusivamente desde celdas verificadas (sin cifras
        inventadas).
      </p>

      <div style={{ display: "grid", gap: "1rem" }}>
        <svg
          role="img"
          aria-label="Grafo conceptual verificado"
          viewBox="0 0 360 120"
          style={{
            width: "100%",
            height: "120px",
            border: "1px solid var(--border-subtle, #cbd5e1)",
            borderRadius: "8px",
          }}
        >
          {edges.map((edge, idx) => {
            const sIdx = Math.max(
              0,
              nodes.findIndex((n) => n.id === edge.source),
            );
            const tIdx = Math.max(
              0,
              nodes.findIndex((n) => n.id === edge.target),
            );
            const x1 = 60 + sIdx * 120;
            const x2 = 60 + tIdx * 120;
            return (
              <line
                key={`${edge.source}-${edge.target}-${idx}`}
                x1={x1}
                y1={60}
                x2={x2}
                y2={60}
                stroke="currentColor"
                strokeOpacity={0.35}
                strokeWidth={2}
              />
            );
          })}
          {nodes.map((node, idx) => {
            const cx = 60 + idx * 120;
            return (
              <g key={node.id}>
                <circle
                  cx={cx}
                  cy={60}
                  r={18}
                  fill="var(--accent-primary, #2563eb)"
                  fillOpacity={0.18}
                  stroke="var(--accent-primary, #2563eb)"
                />
                <text
                  x={cx}
                  y={100}
                  textAnchor="middle"
                  fontSize="11"
                  fill="currentColor"
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              marginBottom: "0.4rem",
            }}
          >
            <BarChart3 size={16} aria-hidden="true" />
            <strong>Métricas verificadas</strong>
          </div>
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
          >
            {rows.map((row) => {
              const widthPct = Math.max(
                4,
                Math.round((Math.abs(row.value) / maxVal) * 100),
              );
              return (
                <div key={`${row.label}-${row.provenance}`}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span>{row.label}</span>
                    <span>
                      <strong>{row.value}</strong>{" "}
                      <code style={{ fontSize: "0.75rem" }}>
                        [{row.provenance}]
                      </code>
                    </span>
                  </div>
                  <div
                    style={{
                      height: "8px",
                      borderRadius: "4px",
                      background: "rgba(148, 163, 184, 0.25)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${widthPct}%`,
                        height: "100%",
                        background: "var(--accent-primary, #2563eb)",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
