import pytest

from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.shared.errors import ValidationError


@pytest.mark.parametrize("form", ["relative", "absolute", "uri", "localhost_uri"])
def test_resolves_local_historical_paths(tmp_path, form):
    path = tmp_path / "synthetic ñ.txt"
    path.write_text("Synthetic file", encoding="utf-8")
    locations = {
        "relative": path.name,
        "absolute": str(path),
        "uri": path.as_uri(),
        "localhost_uri": path.as_uri().replace("file:///", "file://localhost/", 1),
    }
    assert LocalDocumentPathResolver(str(tmp_path)).resolve(locations[form]) == path


@pytest.mark.parametrize("location", [
    "", "../outside.txt", "https://example.invalid/document",
    "file://remote.invalid/document", "file:relative.txt", "file:///document?query=x",
    "file:///document#fragment", "file://[invalid/document",
    "bad\x00file", "bad\nfile", "bad\tfile", "file:///bad%00file", "file:///bad%0Afile",
])
def test_rejects_invalid_locations_without_disclosing_paths(tmp_path, location):
    with pytest.raises(ValidationError) as error:
        LocalDocumentPathResolver(str(tmp_path)).resolve(location)
    assert str(tmp_path) not in str(error.value)


def test_symlinks_remain_within_storage(tmp_path):
    base = tmp_path / "documents"
    base.mkdir()
    inside = base / "inside.txt"
    inside.write_text("Inside", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside", encoding="utf-8")
    (base / "internal-link").symlink_to(inside)
    (base / "external-link").symlink_to(outside)
    (base / "external-directory").symlink_to(tmp_path, target_is_directory=True)
    resolver = LocalDocumentPathResolver(str(base))
    assert resolver.resolve("internal-link") == inside
    for location in ("external-link", "external-directory/outside.txt", str(outside), outside.as_uri()):
        with pytest.raises(ValidationError):
            resolver.resolve(location)
    assert outside.read_text() == "Outside"


def test_missing_files_directories_and_link_loops(tmp_path):
    resolver = LocalDocumentPathResolver(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        resolver.resolve("missing.txt")
    with pytest.raises(ValidationError):
        resolver.resolve(str(tmp_path))
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    with pytest.raises(ValidationError):
        resolver.resolve(str(loop))
