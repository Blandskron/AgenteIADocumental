from pathlib import Path


class FileReader:
    def read_bytes(self, file_path: str) -> bytes:
        return Path(file_path).read_bytes()
