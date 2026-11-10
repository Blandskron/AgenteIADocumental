"""Real raster OCR smoke test for the minimal, archive-free native build."""
from PIL import Image, ImageDraw, ImageFont

from app.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor


def test_native_ocr_preserves_raster_support(tmp_path):
    target = tmp_path / "synthetic.png"
    image = Image.new("RGB", (1200, 180), "white")
    ImageDraw.Draw(image).text((30, 45), "CONTRATO 97 DIAS", fill="black", font=ImageFont.load_default(size=64))
    image.save(target)
    assert "97" in ImageOcrExtractor().extract(str(target))
