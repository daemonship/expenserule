"""Receipt upload endpoint with Pillow preprocessing and LLM parsing."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from expenserule.categorization import suggest_category
from expenserule.database import UPLOADS_DIR, ensure_dirs
from expenserule.llm import parse_receipt, preprocess_file

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload/parse")
async def parse_upload(file: UploadFile) -> JSONResponse:
    """
    Accept a JPEG, PNG, or PDF receipt file.

    1. Validate file type and size.
    2. Save original file to UPLOADS_DIR with a UUID filename.
    3. Preprocess with Pillow (EXIF orientation, RGB, resize) or pdf2image.
    4. Send to GPT-4o-mini and return extracted fields as JSON.

    The returned JSON is shown to the user for review before saving.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Upload a JPEG, PNG, or PDF.",
        )

    raw_bytes = await file.read()

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw_bytes) // 1024} KB). Maximum is 20 MB.",
        )

    # Determine extension from content type
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
    }
    ext = ext_map[file.content_type]

    # Persist original file with a stable UUID so future tasks can reference it
    ensure_dirs()
    upload_id = uuid.uuid4().hex
    stored_path = UPLOADS_DIR / f"{upload_id}{ext}"
    stored_path.write_bytes(raw_bytes)

    # Preprocess and call LLM
    try:
        image_bytes = preprocess_file(raw_bytes, file.content_type)
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"Could not process image: {exc}",
        ) from exc

    try:
        extracted = parse_receipt(image_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM parsing failed: {exc}",
        ) from exc

    # Auto-categorize using correction_memory → lookup → LLM
    categorization = suggest_category(extracted["merchant"])

    return JSONResponse(
        {
            "upload_id": upload_id,
            "merchant": extracted["merchant"],
            "date": extracted["date"],
            "amount": extracted["amount"],
            "category": categorization["category"],
            "schedule_c_line": categorization["schedule_c_line"],
            "category_source": categorization["source"],
        }
    )
