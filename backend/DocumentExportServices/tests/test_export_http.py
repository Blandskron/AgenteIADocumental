from io import BytesIO
import pytest
from pypdf import PdfReader
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def create(client, headers):
    response = client.post("/api/v1/exports/chat-message/pdf", headers=headers, json={
        "title": "Contrato sintetico", "question": "Cual es el plazo?", "answer": "El plazo es de 97 dias.",
        "sources": [{"filename": "synthetic.txt", "page": 4, "content": "El plazo es de 97 dias."}],
        "metadata": {"synthetic": True},
    })
    assert response.status_code == 200
    return response.json()


def test_postgres_export_download_and_owner_filter(client, token_headers, settings, db_session, owner, other_id):
    saved = create(client, token_headers())
    assert saved["status"] == "COMPLETED" and saved["format"] == "PDF"
    assert "storage_path" not in saved and "owner_user_id" not in saved
    assert saved["metadata"]["synthetic"] is True and saved["metadata"]["source_count"] == 1
    assert client.get("/api/v1/exports", headers=token_headers()).json()[0]["export_id"] == saved["export_id"]
    assert client.get("/api/v1/exports?source_type=unmatched", headers=token_headers()).json() == []
    other = token_headers(user_id=int(other_id))
    assert client.get("/api/v1/exports", headers=other).json() == []
    for suffix in ("", "/status", "/download"):
        assert client.get("/api/v1/exports/" + saved["export_id"] + suffix, headers=other).status_code == 404
    downloaded = client.get(saved["download_url"], headers=token_headers())
    assert downloaded.status_code == 200 and downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF-")
    record = db_session.execute(text("SELECT pdf_data,owner_user_id FROM document_exports WHERE export_id=:id"), {"id": saved["export_id"]}).one()
    assert record.owner_user_id == owner
    assert "97 dias" in PdfReader(BytesIO(record.pdf_data)).pages[0].extract_text()
    assert client.get("/api/v1/exports/" + saved["export_id"] + "/status", headers=token_headers()).json()["status"] == "COMPLETED"


def test_health_and_openapi_contract(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/db").json() == {"status": "ok"}
    paths = client.get("/openapi.json").json()["paths"]
    assert len(paths) == 7
    assert "delete" in paths["/api/v1/exports/{export_id}"]
    assert paths["/api/v1/exports/chat-message/pdf"]["post"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in paths["/api/v1/health/db"]["get"]


def test_legacy_storage_obstruction_does_not_affect_database_pdf(client, token_headers, settings):
    settings.export_storage_base_path.write_text("synthetic")
    response = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "synthetic"})
    assert response.status_code == 200
    assert client.get(response.json()["download_url"], headers=token_headers()).status_code == 200
    assert settings.export_storage_base_path.read_text() == "synthetic"