from importlib import import_module
from pathlib import Path

from .models import ExtractedFields


def extract_text_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF certificate.

    Strategy:
    1. Try pdfplumber first (fast, high quality for typed/digital PDFs)
    2. If pdfplumber returns < 50 characters of text, fall back to OCR
    3. If OCR also returns < 50 characters, flag as UNREADABLE

    Returns dict with:
    - "text": full extracted text (all pages concatenated)
    - "pages": list of per-page text
    - "page_count": number of pages
    - "method": "pdfplumber" or "ocr" or "unreadable"
    - "confidence": float 0-1 (1.0 for pdfplumber, 0.7-0.9 for OCR based on quality)
    """
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return {
            "text": "",
            "pages": [],
            "page_count": 0,
            "method": "unreadable",
            "confidence": 0.0,
        }

    plumber_pages: list[str] = []
    page_count = 0

    try:
        pdfplumber = import_module("pdfplumber")
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                plumber_pages.append(page.extract_text() or "")
    except Exception:
        plumber_pages = []

    plumber_text = "\n\n".join(plumber_pages).strip()
    if len(plumber_text) >= 50:
        return {
            "text": plumber_text,
            "pages": plumber_pages,
            "page_count": page_count,
            "method": "pdfplumber",
            "confidence": 1.0,
        }

    ocr_pages: list[str] = []
    ocr_page_count = page_count
    try:
        convert_from_path = import_module("pdf2image").convert_from_path
        pytesseract = import_module("pytesseract")
        images = convert_from_path(str(path))
        ocr_page_count = len(images)
        for image in images:
            ocr_pages.append(pytesseract.image_to_string(image) or "")
    except Exception:
        ocr_pages = []

    ocr_text = "\n\n".join(ocr_pages).strip()
    if len(ocr_text) >= 50:
        confidence = 0.85 if len(ocr_text) >= 200 else 0.5
        return {
            "text": ocr_text,
            "pages": ocr_pages,
            "page_count": ocr_page_count,
            "method": "ocr",
            "confidence": confidence,
        }

    return {
        "text": ocr_text or plumber_text,
        "pages": ocr_pages or plumber_pages,
        "page_count": ocr_page_count if ocr_pages else page_count,
        "method": "unreadable",
        "confidence": 0.0,
    }


def detect_signature(pdf_path: str, page_num: int = 0, region: str = "bottom_20_percent") -> bool:
    """
    Detect if a signature-like mark exists in the expected region.

    Approach:
    1. Convert the specified page to an image (use pdf2image)
    2. Crop to the signature region:
       - "bottom_20_percent": bottom 20% of page (default for most forms)
       - "bottom_30_percent": bottom 30% (for forms with larger signature areas)
    3. Convert to grayscale
    4. Count non-white pixels (< 240 brightness threshold)
    5. If non-white pixel density > 2% of region area, signature is present

    This is intentionally simple — we're detecting presence, not verifying identity.
    """
    try:
        convert_from_path = import_module("pdf2image").convert_from_path
        images = convert_from_path(
            str(pdf_path),
            first_page=page_num + 1,
            last_page=page_num + 1,
        )
        if not images:
            return False

        image = images[0].convert("L")
        width, height = image.size
        start_pct = 0.8 if region == "bottom_20_percent" else 0.7

        top = int(height * start_pct)
        cropped = image.crop((0, top, width, height))
        pixels = list(cropped.getdata())
        if not pixels:
            return False

        non_white = sum(1 for px in pixels if px < 240)
        density = non_white / len(pixels)
        return density > 0.02
    except Exception:
        return False


def extract_certificate(pdf_path: str) -> ExtractedFields:
    """
    Main entry point: extract all available data from a certificate PDF.

    1. Extract text (pdfplumber → OCR fallback)
    2. Detect signature
    3. Return ExtractedFields with:
       - raw_text populated
       - signature_present set
       - extraction_confidence set
       - All other fields remain None (populated in Session 2's parse.py)
    """
    extraction = extract_text_from_pdf(pdf_path)
    signature_present = detect_signature(pdf_path)

    return ExtractedFields(
        raw_text=extraction["text"],
        signature_present=signature_present,
        extraction_confidence=extraction["confidence"],
    )
