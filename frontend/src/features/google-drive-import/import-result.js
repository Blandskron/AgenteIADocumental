export function getImportWarning(result) {
  if (result.status === "COMPLETED") return "";
  return result.errorMessage || "La importación terminó con incidencias. Revisa los documentos importados antes de reintentar.";
}
