"""Expense list, save, and correction memory router."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from expenserule.categories import CATEGORY_LINE, SCHEDULE_C_CATEGORIES
from expenserule.categorization import suggest_category
from expenserule.database import (
    get_expense_years,
    list_expenses,
    save_expense,
    update_expense_category,
    upsert_correction,
)

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SaveExpenseRequest(BaseModel):
    merchant: str = Field(..., min_length=1, max_length=200)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1)
    schedule_c_line: str = Field(..., min_length=1)
    notes: str = Field(default="", max_length=1000)


class UpdateCategoryRequest(BaseModel):
    category: str = Field(..., min_length=1)
    remember: bool = Field(
        default=True,
        description="Store merchant→category in correction_memory for future receipts",
    )


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def expense_list(request: Request) -> HTMLResponse:
    rows = list_expenses()
    expenses = [dict(row) for row in rows]
    total = sum(e["amount"] for e in expenses)
    years = get_expense_years()
    return _templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "expenses": expenses,
            "categories": SCHEDULE_C_CATEGORIES,
            "total": total,
            "years": years,
        },
    )


@router.get("/expenses/partial", response_class=HTMLResponse)
async def expense_list_partial(
    request: Request,
    category_filter: str = "",
    year_filter: str = "",
) -> HTMLResponse:
    """htmx endpoint: returns just the expense table HTML for the filter bar."""
    year = int(year_filter) if year_filter else None
    rows = list_expenses(year=year)
    expenses = [dict(row) for row in rows]
    if category_filter:
        expenses = [e for e in expenses if e["category"] == category_filter]
    total = sum(e["amount"] for e in expenses)
    return _templates.TemplateResponse(
        "partials/expense_table.html",
        {"request": request, "expenses": expenses, "total": total},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_expense_page(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        "new.html",
        {"request": request, "categories": SCHEDULE_C_CATEGORIES},
    )


@router.post("/expenses")
async def save_expense_form(
    merchant: str = Form(...),
    date: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    notes: str = Form(default=""),
    upload_id: str = Form(default=""),
) -> RedirectResponse:
    """Handle HTML form submission from the upload review and manual entry forms."""
    if category not in CATEGORY_LINE:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{category}'.",
        )
    save_expense(
        merchant=merchant,
        date=date,
        amount=amount,
        category=category,
        schedule_c_line=CATEGORY_LINE[category],
        notes=notes,
    )
    return RedirectResponse(url="/", status_code=303)


# ---------------------------------------------------------------------------
# JSON API routes
# ---------------------------------------------------------------------------


@router.get("/api/expenses")
async def api_list_expenses(year: int | None = None) -> JSONResponse:
    """Return expenses as JSON, optionally filtered by year."""
    rows = list_expenses(year=year)
    return JSONResponse([dict(row) for row in rows])


@router.post("/api/expenses")
async def api_save_expense(body: SaveExpenseRequest) -> JSONResponse:
    """
    Persist a new expense.

    Validates that category is one of the 19 Schedule C categories.
    """
    if body.category not in CATEGORY_LINE:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{body.category}'. Must be one of the 19 Schedule C categories.",
        )
    expense_id = save_expense(
        merchant=body.merchant,
        date=body.date,
        amount=body.amount,
        category=body.category,
        schedule_c_line=CATEGORY_LINE[body.category],
        notes=body.notes,
    )
    return JSONResponse({"id": expense_id}, status_code=201)


@router.patch("/api/expenses/{expense_id}/category")
async def api_update_category(expense_id: int, body: UpdateCategoryRequest) -> JSONResponse:
    """
    Update the category on an existing expense.

    When *remember* is True (default), also upserts the merchant→category pair
    into correction_memory so future receipts from the same merchant are
    pre-categorized correctly.
    """
    if body.category not in CATEGORY_LINE:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{body.category}'.",
        )
    line = CATEGORY_LINE[body.category]
    updated = update_expense_category(expense_id, body.category, line)
    if not updated:
        raise HTTPException(status_code=404, detail="Expense not found.")

    if body.remember:
        # Fetch merchant from DB to key correction_memory correctly
        from expenserule.database import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT merchant FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
        if row:
            upsert_correction(row["merchant"], body.category)

    return JSONResponse({"id": expense_id, "category": body.category, "schedule_c_line": line})


@router.get("/api/categories")
async def api_categories() -> JSONResponse:
    """Return the full list of Schedule C categories."""
    return JSONResponse(SCHEDULE_C_CATEGORIES)


@router.get("/api/categorize")
async def api_categorize(merchant: str) -> JSONResponse:
    """
    Suggest a category for a merchant name without saving anything.
    Useful for manual entry forms to pre-populate the category dropdown.
    """
    if not merchant.strip():
        raise HTTPException(status_code=422, detail="merchant must not be empty")
    result = suggest_category(merchant)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def _csv_safe(value: str) -> str:
    """Prefix cells that start with formula-trigger characters to prevent CSV injection."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/export/csv")
async def export_csv(year: int | None = None) -> StreamingResponse:
    """Download all expenses (or a single year) as a CSV file."""
    rows = list_expenses(year=year)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "merchant", "amount", "category", "schedule_c_line", "notes"])
    for row in rows:
        writer.writerow([
            _csv_safe(str(row["date"])),
            _csv_safe(str(row["merchant"])),
            f"{row['amount']:.2f}",
            _csv_safe(str(row["category"])),
            _csv_safe(str(row["schedule_c_line"])),
            _csv_safe(str(row["notes"])),
        ])

    filename = f"expenses-{year}.csv" if year else "expenses.csv"
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
