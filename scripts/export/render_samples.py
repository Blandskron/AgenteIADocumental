"""Generate three synthetic PDF QA fixtures, never load user documents."""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, "/app")
    from app.domain.entities import ChatPdfExport
    from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer
    from app.interfaces.api.v1.schemas.export_schema import ChatPdfExportRequest

    args.output.mkdir(parents=True, exist_ok=False)
    cases = {
        "spanish": {"title": "Respuesta documental: condiciones del contrato", "question": "¿Cuál es el plazo de entrega?",
                    "answer": "El plazo es de 97 días.\nLa documentación debe incluir información técnica, año y número de versión.",
                    "sources": [{"filename": "Contrato A & B <2026>.pdf", "page": 4, "snippet": "Entrega: 97 días. Acción y revisión."}]},
        "unicode": {"title": "Unicode: español, Ελληνικά, Кириллица", "question": "¿Se preservan los caracteres?",
                    "answer": "Sí: Peña, pingüino, acción, € y Ω.\nΕλληνικά: Καλημέρα. Кириллица: Привет.\n<b>HTML literal</b> & **Markdown literal**."},
        "long-table": {"title": "Fuentes extensas: informe de revisión", "question": "¿Se mantienen legibles las fuentes?",
                       "answer": "Esta muestra comprueba tablas con celdas largas y encabezados repetidos.",
                       "sources": [{"filename": "Documento con nombre descriptivo y caracteres españoles " * 3,
                                    "page": index + 1, "snippet": "Fragmento de prueba legible, con términos técnicos y revisión de información. " * 15}
                                   for index in range(12)]},
    }
    for name, value in cases.items():
        payload = ChatPdfExportRequest(**value)
        export = ChatPdfExport(payload.title, payload.question, payload.answer, [source.model_dump() for source in payload.sources])
        (args.output / (name + ".pdf")).write_bytes(ChatPdfRenderer().render(export))
    print("Three synthetic PDF samples generated.")


if __name__ == "__main__":
    main()
