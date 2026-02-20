"""First-run setup router."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from expenserule.database import save_api_key

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse("setup.html", {"request": request})


@router.post("/setup")
async def save_setup(api_key: str = Form(...)) -> RedirectResponse:
    save_api_key(api_key)
    return RedirectResponse(url="/", status_code=303)
