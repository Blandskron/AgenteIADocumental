"""Read-only POSIX descriptor traversal for explicitly reviewed legacy files."""
import os
import stat
from hashlib import sha256
from pathlib import Path

from app.config.export_limits import MAX_PDF


def read_legacy(base, stored_path):
    base, path = Path(base), Path(stored_path)
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Legacy migration requires POSIX descriptor support.")
    if not base.is_absolute() or path.parent != base or path.name in ("", ".", "..") or ".." in base.parts:
        raise ValueError("Invalid legacy location.")
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    file = None
    try:
        for part in base.parts[1:]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        file = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(file)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_PDF:
            raise ValueError("Invalid legacy resource.")
        data = bytearray()
        while len(data) <= MAX_PDF:
            chunk = os.read(file, min(65536, MAX_PDF + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(file)
        def signature(entry):
            return (entry.st_dev, entry.st_ino, entry.st_size, entry.st_mtime_ns, entry.st_ctime_ns)
        if (signature(before) != signature(after) or len(data) != before.st_size
                or len(data) > MAX_PDF or not data.startswith(b"%PDF-")):
            raise ValueError("Legacy resource changed or is invalid.")
        return bytes(data), sha256(data).hexdigest()
    finally:
        if file is not None:
            os.close(file)
        os.close(directory)
