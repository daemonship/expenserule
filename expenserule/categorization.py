"""Auto-categorization: correction_memory → lookup table → LLM fallback."""

from __future__ import annotations

import json

from expenserule.categories import CATEGORY_LINE, MERCHANT_LOOKUP, SCHEDULE_C_CATEGORIES
from expenserule.database import get_correction

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CATEGORY_NAMES = [cat["name"] for cat in SCHEDULE_C_CATEGORIES]

_LLM_SYSTEM = (
    "You are an IRS Schedule C tax categorization assistant. "
    "Given a merchant name, pick the single most appropriate category from the list below. "
    "Reply ONLY with the category name exactly as written — no punctuation, no explanation.\n\n"
    "Categories:\n" + "\n".join(f"- {name}" for name in _CATEGORY_NAMES)
)


def _normalize(merchant: str) -> str:
    """Lowercase and strip a merchant name for table lookups."""
    return merchant.strip().lower()


def _lookup_table(merchant: str) -> str | None:
    """Check the built-in merchant lookup table. Returns category name or None."""
    key = _normalize(merchant)
    if key in MERCHANT_LOOKUP:
        return MERCHANT_LOOKUP[key]
    # Try substring match: any lookup key contained in the merchant name
    for lookup_key, category in MERCHANT_LOOKUP.items():
        if lookup_key in key:
            return category
    return None


def _llm_suggest(merchant: str) -> str:
    """Ask GPT-4o-mini to categorize this merchant. Returns a category name."""
    from openai import OpenAI

    from expenserule.database import load_api_key

    client = OpenAI(api_key=load_api_key())
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _LLM_SYSTEM},
            {"role": "user", "content": f"Merchant: {merchant}"},
        ],
        max_tokens=32,
        temperature=0,
    )
    suggestion = response.choices[0].message.content.strip()
    # Validate — fall back to Other Expenses if LLM returns something unexpected
    if suggestion in _CATEGORY_NAMES:
        return suggestion
    return "Other Expenses"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest_category(merchant: str) -> dict[str, str]:
    """
    Return the best category for *merchant* using a three-tier priority:

    1. correction_memory  (user's explicit past corrections — highest priority)
    2. built-in lookup table  (~200 known merchants)
    3. LLM suggestion  (GPT-4o-mini fallback)

    Returns a dict::

        {
            "category":        str,   # Schedule C category name
            "schedule_c_line": str,   # e.g. "18"
            "source":          str,   # "correction_memory" | "lookup" | "llm"
        }
    """
    # 1. Correction memory
    remembered = get_correction(merchant)
    if remembered and remembered in CATEGORY_LINE:
        return {
            "category": remembered,
            "schedule_c_line": CATEGORY_LINE[remembered],
            "source": "correction_memory",
        }

    # 2. Built-in lookup table
    from_table = _lookup_table(merchant)
    if from_table:
        return {
            "category": from_table,
            "schedule_c_line": CATEGORY_LINE[from_table],
            "source": "lookup",
        }

    # 3. LLM fallback
    llm_category = _llm_suggest(merchant)
    return {
        "category": llm_category,
        "schedule_c_line": CATEGORY_LINE.get(llm_category, "27a"),
        "source": "llm",
    }
