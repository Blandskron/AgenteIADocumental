from concurrent.futures import ThreadPoolExecutor
import io
import struct
from threading import Barrier
import zlib

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.avatars import MAX_UPLOAD_BYTES, normalize_avatar
from app.main import create_app


def image_bytes(format="PNG", color="red", size=(8, 4), **options):
    output = io.BytesIO()
    with Image.new("RGB", size, color) as image:
        image.save(output, format=format, **options)
    return output.getvalue()


def upload(client, headers, content=None, version=0, name="../../synthetic.png"):
    return client.post("/api/v1/profile/upload", headers=headers,
                       data={"expected_version": str(version)},
                       files={"file": (name, content if content is not None else image_bytes(), "application/octet-stream")})


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_formats_are_decoded_reencoded_and_bounded(format):
    content = normalize_avatar(image_bytes(format, size=(1600, 400)))
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "JPEG" and image.mode == "RGB" and image.size == (1024, 256)
        assert not image.getexif() and "icc_profile" not in image.info
    assert len(content) <= 1048576


def test_metadata_exif_orientation_and_trailing_bytes_removed():
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("description", "private-synthetic-metadata")
    assert b"private-synthetic-metadata" not in normalize_avatar(image_bytes(pnginfo=metadata) + b"private-synthetic-tail")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private-synthetic-description"
    content = normalize_avatar(image_bytes("JPEG", exif=exif, icc_profile=b"private-icc"))
    with Image.open(io.BytesIO(content)) as image:
        assert image.size == (4, 8) and not image.getexif() and "icc_profile" not in image.info
    assert b"private" not in content


def test_transparency_is_flattened_to_white():
    output = io.BytesIO()
    with Image.new("RGBA", (2, 2), (0, 0, 0, 0)) as image:
        image.save(output, format="PNG")
    with Image.open(io.BytesIO(normalize_avatar(output.getvalue()))) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("format", ["GIF", "BMP", "TIFF"])
def test_other_codecs_rejected(format):
    with pytest.raises(ValueError):
        normalize_avatar(image_bytes(format))


@pytest.mark.parametrize("format", ["PNG", "WEBP"])
def test_animation_rejected(format):
    output = io.BytesIO()
    with Image.new("RGB", (2, 2), "red") as first, Image.new("RGB", (2, 2), "blue") as second:
        first.save(output, format=format, save_all=True, append_images=[second], duration=100, loop=0)
    with pytest.raises(ValueError):
        normalize_avatar(output.getvalue())


@pytest.mark.parametrize("size", [(4000, 4000), (8193, 1), (100000, 100000)])
def test_dimensions_rejected_before_pixel_allocation(size):
    content = bytearray(image_bytes())
    content[16:24] = struct.pack("!II", *size)
    content[29:33] = struct.pack("!I", zlib.crc32(content[12:29]))
    with pytest.raises(ValueError):
        normalize_avatar(bytes(content))


def test_private_lifecycle_and_contact_preservation(client, token_headers, db_session, profile_id):
    headers = token_headers()
    assert client.get("/api/v1/profile/avatar", headers=headers).status_code == 404
    created = upload(client, headers)
    assert created.status_code == 200 and created.json()["version"] == 1
    path = created.json()["profile_picture_url"]
    assert path == "/api/v1/profile/avatar?version=1"
    assert client.get(path).status_code == 401
    response = client.get(path, headers=headers)
    original = response.content
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.format == "JPEG"
    changed = client.put("/api/v1/profile", headers=headers, json={"expected_version": 1, "email": "synthetic@example.com"})
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert client.get(changed.json()["profile_picture_url"], headers=headers).content == original
    assert client.get(path, headers=headers).status_code == 404
    assert upload(client, headers, version=1).status_code == 409
    replaced = upload(client, headers, image_bytes(color="blue"), version=2)
    assert replaced.status_code == 200 and replaced.json()["email"] == "synthetic@example.com"
    assert client.get(replaced.json()["profile_picture_url"], headers=headers).content != original
    assert client.request("DELETE", "/api/v1/profile/avatar", headers=headers, json={"expected_version": 2}).status_code == 409
    cleared = client.request("DELETE", "/api/v1/profile/avatar", headers=headers, json={"expected_version": 3})
    assert cleared.status_code == 200 and cleared.json()["profile_picture_url"] is None
    assert client.get("/api/v1/profile/avatar", headers=headers).status_code == 404
    row = db_session.execute(text("SELECT avatar_ready, avatar_data FROM user_profiles WHERE user_id=:id"), {"id": profile_id}).one()
    assert row.avatar_ready is False and row.avatar_data is None


@pytest.mark.parametrize("claims", [{}, {"is_superadmin": True, "roles": ["SUPERADMIN"]},
                                   {"tenant_memberships": [{"tenant_id": "synthetic", "role": "TENANT_ADMIN"}]}])
def test_no_role_can_fetch_another_owners_photo(client, token_headers, other_id, claims):
    own = token_headers(**claims)
    other = token_headers(user_id=int(other_id))
    first = upload(client, own).json()
    second = upload(client, other, image_bytes(color="blue")).json()
    assert first["profile_picture_url"] == second["profile_picture_url"]
    assert client.get(second["profile_picture_url"], headers=own).content != client.get(second["profile_picture_url"], headers=other).content
    assert client.get("/api/v1/profiles/" + other_id + "/avatar", headers=own).status_code == 404
    assert client.get("/static/" + "a" * 32 + ".png").status_code == 404


@pytest.mark.parametrize("version", [None, "", "00", "-1", "true", str(2**63), "1" * 100])
def test_multipart_version_is_required_and_bounded(client, token_headers, version):
    response = client.post("/api/v1/profile/upload", headers=token_headers(),
                           data={} if version is None else {"expected_version": version},
                           files={"file": ("synthetic.png", image_bytes(), "image/png")})
    assert response.status_code in {400, 422}


def test_limits_corrupt_images_and_parser_shape(client, token_headers):
    headers = token_headers()
    assert upload(client, headers, b"not an image").status_code == 400
    assert upload(client, headers, image_bytes()[:40]).status_code == 400
    assert upload(client, headers, b"x" * (MAX_UPLOAD_BYTES + 1)).status_code == 413
    assert client.post("/api/v1/profile/upload", headers=headers,
                       content=iter([b"x" * MAX_UPLOAD_BYTES, b"x" * 65537])).status_code == 413
    duplicate = client.post("/api/v1/profile/upload", headers=headers, data={"expected_version": "0"},
                            files=[("file", ("a.png", image_bytes())), ("file", ("b.png", image_bytes()))])
    assert duplicate.status_code == 400
    assert client.post("/api/v1/profile/upload", headers=headers, data={"expected_version": "0", "extra": "private"},
                       files={"file": ("a.png", image_bytes())}).status_code == 400


def test_legacy_urls_are_hidden_and_arbitrary_urls_forbidden(client, token_headers, db_session, profile_id):
    db_session.execute(text("INSERT INTO user_profiles(user_id,profile_picture_url) VALUES (:id,'https://private.invalid/static/old.png')"), {"id": profile_id})
    result = client.get("/api/v1/profile", headers=token_headers())
    assert result.json()["profile_picture_url"] is None and "private.invalid" not in result.text
    assert client.put("/api/v1/profile", headers=token_headers(), json={
        "expected_version": 1, "profile_picture_url": "https://external.invalid/photo.jpg",
    }).status_code == 422


def test_failed_commit_restores_previous_image(committed_engine, settings, token_headers, monkeypatch):
    with TestClient(create_app(settings)) as client:
        saved = upload(client, token_headers()).json()
        previous = client.get(saved["profile_picture_url"], headers=token_headers()).content
        def fail(*args, **kwargs):
            raise SQLAlchemyError("private-synthetic-failure")
        with monkeypatch.context() as patch:
            patch.setattr(Session, "commit", fail)
            result = upload(client, token_headers(), image_bytes(color="blue"), version=1)
            assert result.status_code == 503 and "private" not in result.text
        assert client.get(saved["profile_picture_url"], headers=token_headers()).content == previous
        assert client.get("/api/v1/profile", headers=token_headers()).json()["version"] == 1
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(saved["profile_picture_url"], headers=token_headers()).content == previous


def test_parallel_photo_writes_have_one_winner(committed_engine, settings, token_headers):
    barrier = Barrier(2)
    def write(color):
        with TestClient(create_app(settings)) as client:
            barrier.wait(timeout=5)
            return upload(client, token_headers(), image_bytes(color=color)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, color) for color in ("red", "blue")]
        assert sorted(future.result(timeout=10) for future in futures) == [200, 409]


def test_processing_slots_return_after_failures(client, token_headers):
    from app.interfaces.api.v1.routes.profile_routes import avatar_slots
    assert avatar_slots.acquire(blocking=False) and avatar_slots.acquire(blocking=False)
    try:
        assert upload(client, token_headers()).status_code == 503
    finally:
        avatar_slots.release()
        avatar_slots.release()
    assert upload(client, token_headers(), b"invalid").status_code == 400
    assert upload(client, token_headers()).status_code == 200
