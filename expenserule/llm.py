"""LLM-based receipt parsing with Pillow preprocessing."""

import base64
import io
import json
from pathlib import Path

from PIL import Image, ImageOps
from openai import OpenAI

from expenserule.database import load_api_key

# Max dimension (pixels) for the longest side before sending to LLM
MAX_IMAGE_DIM = 2048

EXTRACTION_PROMPT = """\
You are a receipt parser. Extract the following fields from this receipt image:
- merchant: The store or vendor name (string)
- date: The transaction date in YYYY-MM-DD format (string, or null if not found)
- amount: The total amount paid as a number without currency symbols (number, or null if not found)

Respond ONLY with a JSON object containing exactly these three keys: merchant, date, amount.
Do not include any explanation or additional text.

Example: {"merchant": "Staples", "date": "2024-03-15", "amount": 42.97}
"""


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    """Rotate/flip the image according to its EXIF orientation tag."""
    return ImageOps.exif_transpose(img)


def _preprocess_image(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation, convert to RGB, and resize if too large."""
    img = _apply_exif_orientation(img)
    img = img.convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def preprocess_file(file_bytes: bytes, content_type: str) -> bytes:
    """
    Accept raw file bytes and MIME type.
    Return JPEG bytes of the preprocessed image ready to send to the LLM.
    Handles JPEG, PNG, and PDF (first page via pdf2image).
    """
    if content_type == "application/pdf":
        from pdf2image import convert_from_bytes  # lazy import — optional dep

        pages = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=200)
        if not pages:
            raise ValueError("PDF produced no pages")
        img = pages[0]
    else:
        img = Image.open(io.BytesIO(file_bytes))

    img = _preprocess_image(img)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def parse_receipt(image_bytes: bytes) -> dict:
    """
    Send preprocessed JPEG bytes to GPT-4o-mini vision and return extracted fields.

    Returns a dict with keys: merchant (str), date (str|None), amount (float|None).
    Raises on API or JSON parse errors.
    """
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ],
            }
        ],
        max_tokens=256,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps in ```json ... ```
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    parsed = json.loads(raw)

    return {
        "merchant": str(parsed.get("merchant") or "").strip(),
        "date": parsed.get("date") or None,
        "amount": float(parsed["amount"]) if parsed.get("amount") is not None else None,
    }
