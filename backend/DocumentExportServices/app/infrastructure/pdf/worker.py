"""Isolated, bounded renderer. Only PDF bytes reach stdout; no credentials are required."""
import json
import os
import sys

from app.config.export_limits import MAX_BODY
from app.domain.entities import ChatPdfExport
from app.shared.errors import ValidationError


def main():
    try:
        if os.name == "posix":
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer

        data = sys.stdin.buffer.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValidationError()
        payload = json.loads(data)
        sys.stdout.buffer.write(ChatPdfRenderer().render(ChatPdfExport(**payload)))
    except ValidationError:
        raise SystemExit(2) from None
    except Exception:
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
