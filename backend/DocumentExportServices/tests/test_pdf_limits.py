import asyncio
import json
from io import BytesIO

import pytest
from pydantic import ValidationError as SchemaError
from pypdf import PdfReader

from app.config.body_limits import ExportBodyLimits
from app.config.export_limits import MAX_BODY
from app.domain.entities import ChatPdfExport
from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer
from app.infrastructure.pdf.isolated_renderer import IsolatedPdfRenderer
from app.interfaces.api.v1.schemas.export_schema import ChatPdfExportRequest
from app.shared.errors import ValidationError


@pytest.mark.parametrize("payload", [
    {"answer": " "}, {"answer": "x" * 50001}, {"answer": "x", "unexpected": "x"},
    {"answer": "x", "title": " "}, {"answer": "x", "title": "x" * 161},
    {"answer": "x", "sources": [{}] * 41}, {"answer": "x", "sources": [{"filename": "x", "unknown": 1}]},
    {"answer": "x", "sources": [{"page": True}]}, {"answer": "x", "sources": [{"score": float("inf")}]},
    {"answer": "x", "metadata": {"nested": [[[[["deep"]]]]]}},
    {"answer": "x", "metadata": {"large": "x" * 2049}},
    {"answer": "x", "metadata": {"bad": float("nan")}}, {"answer": "x", "metadata": {"bad": 2**100}},
    {"answer": "x\x00"}, {"answer": "x\u202ey"}, {"answer": "unsupported 😀"},
])
def test_invalid_inputs_are_bounded(payload):
    with pytest.raises(SchemaError):
        ChatPdfExportRequest(**payload)


def test_unicode_literal_markup_and_embedded_fonts():
    payload = ChatPdfExportRequest(title="Español Ελληνικά Кириллица", answer="Peña: 97 días, Ω y Ж.\n<img src='https://invalid/x'> **literal** & <b>texto</b>")
    content = ChatPdfRenderer().render(ChatPdfExport(payload.title, payload.question, payload.answer,
                                                    [{"filename": "A & B <C>", "page": 3, "content": "árbol y acción"}]))
    reader = PdfReader(BytesIO(content))
    text = reader.pages[0].extract_text()
    for expected in ["Peña", "97 días", "Ω", "Ж", "<img", "**literal**", "A & B <C>", "árbol"]:
        assert expected in text
    assert not reader.pages[0].get("/Annots")
    fonts = reader.pages[0]["/Resources"]["/Font"]
    assert any(font.get_object().get("/FontDescriptor", {}).get_object().get("/FontFile2") for font in fonts.values()
               if font.get_object().get("/FontDescriptor"))


def test_long_cells_wrap_and_repeat_header():
    sources = [{"filename": "Documento extenso " * 8, "page": index + 1,
                "content": ("Fragmento legible con ñ y &. " * 45)} for index in range(12)]
    content = ChatPdfRenderer().render(ChatPdfExport("Fuentes extensas", "Pregunta", "Respuesta", sources))
    pages = PdfReader(BytesIO(content)).pages
    assert 2 <= len(pages) <= 20
    assert all("Documento" in page.extract_text() for page in pages[1:])
    assert "Fragmento legible" in pages[-1].extract_text()


def test_page_limit_stops_build_without_output():
    with pytest.raises(ValidationError):
        ChatPdfRenderer().render(ChatPdfExport("Límite", "", "Línea de texto\n" * 2000))


def test_real_isolated_worker_returns_pdf():
    content = IsolatedPdfRenderer().render(ChatPdfExport("Aislado", "", "Respuesta sintética"))
    assert "Respuesta sintética" in PdfReader(BytesIO(content)).pages[0].extract_text()


def test_actual_output_limit_rejects_built_pdf(monkeypatch):
    monkeypatch.setattr("app.infrastructure.pdf.chat_pdf_renderer.MAX_PDF", 1024)
    with pytest.raises(ValidationError):
        ChatPdfRenderer().render(ChatPdfExport("Salida acotada", "", "PDF demasiado grande para este límite de prueba"))


def test_worker_deadline_kills_and_reaps_process(monkeypatch):
    import subprocess
    import sys
    from app.shared.errors import ExportLimitError
    original, processes = subprocess.Popen, []
    def stalled(*args, **kwargs):
        process = original([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr("app.infrastructure.pdf.isolated_renderer.subprocess.Popen", stalled)
    monkeypatch.setattr("app.infrastructure.pdf.isolated_renderer.RENDER_SECONDS", .05)
    with pytest.raises(ExportLimitError):
        IsolatedPdfRenderer().render(ChatPdfExport("Timeout", "", "synthetic"))
    assert processes[0].poll() is not None


@pytest.mark.parametrize("declared", [False, True])
def test_actual_http_body_limit_before_downstream(declared):
    async def scenario():
        called, sent = [], []
        async def app(*args): called.append(True)
        middleware = ExportBodyLimits(app)
        chunks = iter([{"type": "http.request", "body": b"x" * (MAX_BODY // 2), "more_body": True},
                       {"type": "http.request", "body": b"x" * (MAX_BODY // 2 + 1)}])
        async def receive(): return next(chunks)
        async def send(message): sent.append(message)
        headers = [(b"content-length", str(MAX_BODY + 1).encode())] if declared else []
        await middleware({"type": "http", "method": "POST", "headers": headers}, receive, send)
        assert not called and sent[0]["status"] == 413
    asyncio.run(scenario())


def test_request_slots_reject_third_and_recover_after_disconnect():
    async def scenario():
        entered, release = asyncio.Queue(), asyncio.Event()
        async def app(*args): pass
        middleware = ExportBodyLimits(app)
        async def blocked():
            await entered.put(True)
            await release.wait()
            return {"type": "http.disconnect"}
        async def send(message): pass
        scope = {"type": "http", "method": "POST", "headers": []}
        tasks = [asyncio.create_task(middleware(scope, blocked, send)) for _ in range(2)]
        await entered.get()
        await entered.get()
        sent = []
        async def collect(message): sent.append(message)
        await middleware(scope, blocked, collect)
        assert sent[0]["status"] == 503 and json.loads(sent[1]["body"])["detail"] == "Export capacity is busy."
        release.set()
        await asyncio.gather(*tasks)
        assert middleware.slots.acquire(False)
        middleware.slots.release()
    asyncio.run(scenario())
