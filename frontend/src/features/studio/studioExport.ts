export interface VerifiedEvidenceRow {
  label: string;
  value: number;
  provenance: string;
}

const FORMULA_PREFIXES = ["=", "+", "-", "@", "\t", "\r"];

export function sanitizeCsvCell(raw: string): string {
  const text = String(raw ?? "");
  const neutralized =
    text.length > 0 && FORMULA_PREFIXES.includes(text[0]) ? `'${text}` : text;
  if (/[",\n\r]/.test(neutralized)) {
    return `"${neutralized.replaceAll('"', '""')}"`;
  }
  return neutralized;
}

export function buildVerifiedEvidenceCsv(rows: VerifiedEvidenceRow[]): string {
  const header = ["Indicador", "Valor", "Procedencia"].join(",");
  const body = rows.map((row) =>
    [
      sanitizeCsvCell(row.label),
      sanitizeCsvCell(String(row.value)),
      sanitizeCsvCell(row.provenance),
    ].join(","),
  );
  return [header, ...body].join("\n") + "\n";
}

export function triggerSafeFileDownload(
  content: string,
  filename: string,
  mimeType: string,
): void {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
