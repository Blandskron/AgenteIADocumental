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

      <div className="ui-stack-md">
        <svg
          role="img"
          aria-label="Grafo conceptual verificado"
          viewBox="0 0 360 120"
          className="ui-concept-svg"
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
                  fill="var(--accent)"
                  fillOpacity={0.18}
                  stroke="var(--accent)"
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

        <div className="ui-stack-sm">
          <div className="settings-ai-card-title">
            <BarChart3 size={16} aria-hidden="true" />
            <strong>Métricas verificadas</strong>
          </div>
          <div className="ui-stack-sm">
            {rows.map((row) => {
              const widthPct = Math.max(
                4,
                Math.round((Math.abs(row.value) / maxVal) * 100),
              );
              return (
                <div key={`${row.label}-${row.provenance}`}>
                  <div className="ui-metric-header">
                    <span>{row.label}</span>
                    <span>
                      <strong>{row.value}</strong>{" "}
                      <code>[{row.provenance}]</code>
                    </span>
                  </div>
                  <div className="ui-progress-track">
                    <div
                      className="ui-progress-fill"
                      style={{ width: `${widthPct}%` }}
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
