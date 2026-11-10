import type { BlobResponse } from "@/shared/api/types.ts";
export async function savePdf(
  file: BlobResponse,
  filename: string,
  current = () => true,
  browser = globalThis,
) {
  if (
    file?.contentType?.split(";")[0].trim().toLowerCase() !==
      "application/pdf" ||
    !(file.blob instanceof Blob) ||
    file.blob.size === 0 ||
    file.blob.size > 1048576 ||
    (await file.blob.slice(0, 5).text()) !== "%PDF-"
  ) {
    throw new Error("La descarga no contiene un PDF válido.");
  }
  if (!current()) return false;
  const url = browser.URL.createObjectURL(file.blob);
  let link;
  try {
    link = browser.document.createElement("a");
    link.href = url;
    link.download = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.pdf$/.test(filename)
      ? filename
      : "respuesta-documental.pdf";
    browser.document.body.appendChild(link);
    link.click();
    return true;
  } finally {
    try {
      link?.remove();
    } finally {
      browser.URL.revokeObjectURL(url);
    }
  }
}
