export function getImportWarning(result: {
  status: string;
  errorMessage?: string;
}) {
  if (result.status === "COMPLETED") return "";
  return (
    result.errorMessage ||
    "La importación terminó con incidencias. Revisa los documentos importados antes de reintentar."
  );
}
