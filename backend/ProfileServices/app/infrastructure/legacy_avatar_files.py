import os
from pathlib import Path
import stat


def open_directory(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Descriptor-based absolute directory access is required.")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def read_regular_file(directory: Path, name: str, limit: int) -> bytes:
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("A single file name is required.")
    root = open_directory(directory)
    descriptor = None
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("Unsupported legacy file.")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Legacy file exceeds limits.")
        return content
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root)
