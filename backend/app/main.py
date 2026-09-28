from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.reports import router as reports_router
from app.core.config import ALLOWED_ORIGINS

app = FastAPI(title="AI Clinical Document Reviewer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(reports_router, prefix="/api")


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Avoid leaking database details and give clients a retryable response."""
    return JSONResponse(status_code=503, content={"detail": "The review could not be saved or loaded. Please retry."})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
