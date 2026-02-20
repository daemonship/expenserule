"""CLI entrypoint for ExpenseRule."""

import uvicorn


def main() -> None:
    """Start the ExpenseRule web server."""
    uvicorn.run(
        "expenserule.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    main()
