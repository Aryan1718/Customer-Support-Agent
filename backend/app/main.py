from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from database import check_connection

app = FastAPI(title="Customer Support Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Customer Support Agent API is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/db")
async def database_health() -> dict[str, str]:
    try:
        check_connection()
    except (RuntimeError, SQLAlchemyError) as exc:
        return {"status": "unhealthy", "detail": str(exc)}

    return {"status": "healthy"}
