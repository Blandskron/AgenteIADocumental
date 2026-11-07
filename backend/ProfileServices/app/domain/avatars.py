import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_AVATAR_BYTES = 1024 * 1024
MAX_PIXELS = 12_000_000


def normalize_avatar(content: bytes) -> bytes:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Invalid avatar size.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as source:
                if (source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "n_frames", 1) != 1
                        or max(source.size) > 8192 or source.width * source.height > MAX_PIXELS):
                    raise ValueError("Unsupported avatar.")
                source.load()
                with ImageOps.exif_transpose(source) as oriented:
                    oriented.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    with oriented.convert("RGBA") as rgba:
                        with Image.new("RGB", rgba.size, "white") as clean:
                            clean.paste(rgba, mask=rgba.getchannel("A"))
                            output = io.BytesIO()
                            clean.save(output, format="JPEG", quality=85)
        normalized = output.getvalue()
        if len(normalized) > MAX_AVATAR_BYTES:
            raise ValueError("Avatar output exceeds limits.")
        return normalized
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Invalid avatar image.") from None
