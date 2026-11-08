import json
import os
import subprocess
import sys
from dataclasses import asdict

from app.config.export_limits import MAX_PDF, RENDER_SECONDS
from app.shared.errors import ExportGenerationError, ExportLimitError


class IsolatedPdfRenderer:
    def render(self, export):
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        process = subprocess.Popen([sys.executable, "-B", "-m", "app.infrastructure.pdf.worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
        try:
            content, _ = process.communicate(json.dumps(asdict(export), ensure_ascii=False).encode(), timeout=RENDER_SECONDS)
        except BaseException as error:
            process.kill()
            process.communicate()
            if isinstance(error, subprocess.TimeoutExpired):
                raise ExportLimitError("PDF generation deadline exceeded.") from None
            raise ExportGenerationError("PDF generation stopped.") from None
        if process.returncode == 2:
            raise ExportLimitError("PDF exceeds generation limits.")
        if process.returncode or not content.startswith(b"%PDF-") or len(content) > MAX_PDF:
            raise ExportGenerationError("PDF generation failed.")
        return content
