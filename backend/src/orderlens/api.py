"""The HTTP API."""

from fastapi import FastAPI

app = FastAPI(title="OrderLens")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the server is up."""
    return {"status": "ok"}
