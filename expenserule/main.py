"""FastAPI application entry point for ExpenseRule."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from expenserule.database import init_db, is_first_run
from expenserule.routers import expenses, setup

# Resolve the package directory so static/template paths are absolute
PKG_DIR = Path(__file__).parent

app = FastAPI(title="ExpenseRule", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=PKG_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(PKG_DIR / "templates"))

app.include_router(setup.router)
app.include_router(expenses.router)


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.middleware("http")
async def first_run_gate(request: Request, call_next):
    """Redirect to /setup when no API key is configured yet."""
    if is_first_run() and request.url.path not in ("/setup", "/static"):
        # Allow static assets through so the setup page can load CSS
        if not request.url.path.startswith("/static"):
            return RedirectResponse(url="/setup")
    return await call_next(request)
