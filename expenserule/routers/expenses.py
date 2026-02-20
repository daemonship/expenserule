"""Expense list and manual entry router (stub for Task 4)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def expense_list(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse("index.html", {"request": request, "expenses": []})
