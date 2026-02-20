# ExpenseRule

Automated receipt categorization for freelancers. Snap a photo of a receipt,
get the merchant, date, and amount extracted by GPT-4o-mini, and have it
auto-assigned to the correct Schedule C line.

## Status

> 🚧 In active development — not yet production ready

| Feature | Status | Notes |
|---------|--------|-------|
| Project scaffold & CI | ✅ Complete | FastAPI, SQLite, Pico CSS |
| Receipt upload & parsing | ✅ Complete | Pillow preprocessing + GPT-4o-mini vision |
| Categorization engine | ✅ Complete | 200-merchant lookup, correction memory, LLM fallback |
| Web UI | ✅ Complete | Expense list, upload flow, manual entry, first-run setup |
| CSV export with year filter | ✅ Complete | `/export/csv?year=YYYY`, CSV injection prevention |
| PR review | 🚧 In Progress | |
| Push & open PR | 📋 Planned | |

## Quick start

```bash
pip install .
expenserule        # opens http://127.0.0.1:8765 in your browser
```

On first run you will be prompted for your OpenAI API key. It is stored in
`~/.expenserule/openai_api_key` with `600` permissions (owner-read only).

## Requirements

- Python 3.11+
- An OpenAI API key (GPT-4o-mini vision)
- `poppler-utils` system package (for PDF receipt support via pdf2image)

## Data storage

All data lives locally in `~/.expenserule/`:

```
~/.expenserule/
├── expenses.db        ← SQLite database
├── openai_api_key     ← API key (chmod 600)
└── uploads/           ← Original receipt files
```
