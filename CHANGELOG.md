# Changelog

All notable changes to ExpenseRule are documented here.

## [1.0.0] — 2026-02-20 (MVP)

### Added

- **Project scaffold** — FastAPI application with SQLite, Pico CSS, CLI entrypoint (`expenserule`), and first-run detection
- **SQLite schema** — `expenses` table (id, merchant, date, amount, category, schedule_c_line, notes, created_at) and `correction_memory` table (merchant, category)
- **Receipt upload & LLM parsing** — POST `/upload` accepts JPEG, PNG, and PDF; Pillow preprocessing (resize, RGB normalization, EXIF-corrected orientation); PDF→image via pdf2image; GPT-4o-mini vision extracts merchant name, date, and total amount
- **Schedule C category model** — 19 categories with line numbers as a static data structure
- **Merchant lookup table** — 200-entry default mapping (e.g., Adobe→Office Expenses Line 18, Uber→Car and Truck Line 9)
- **Correction memory** — merchant→category upserted on every user correction; takes priority over defaults and LLM suggestions
- **LLM categorization fallback** — for merchants not in lookup or correction memory, GPT-4o-mini suggests the Schedule C category
- **Web UI (htmx + Pico CSS)** — first-run privacy/API key screen; receipt upload with editable field review; manual entry form; expense list with htmx-powered category and date-range filtering; no JS build pipeline
- **CSV export** — `GET /export/csv?year=YYYY`; `Content-Disposition: attachment` download header; CSV injection prevention via proper field quoting; year selector on expense list page
