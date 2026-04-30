"""
FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore

from config import API_HOST, API_PORT, CORS_ORIGINS
from database.db import init_db, check_db_connection
from api.session_routes import router as session_router
from api.profile_routes import router as profile_router
from api.progress_routes import router as progress_router
from api.voice_routes import router as voice_router
from api.auth_routes import router as auth_router

# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan

def _run_migrations():
    from database.db import engine
    from sqlalchemy import text # type: ignore
    migrations = [
        # Widen overall_level: 'unassessed' is 10 chars, was VARCHAR(5)
        "ALTER TABLE learner_profiles ALTER COLUMN overall_level TYPE VARCHAR(15)",
        # Widen skill level column too (defensive)
        "ALTER TABLE skill_levels ALTER COLUMN level TYPE VARCHAR(15)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"Migration OK: {sql}")
            except Exception as e:
                conn.rollback()
                # "already correct size" shows as a no-op error we can safely ignore
                logger.debug(f"Migration skipped (already applied or irrelevant): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting nib.ai Language Tutor API...")
    init_db()
    if check_db_connection():
        logger.info("Database connection OK")
        _run_migrations()
    else:
        logger.error("Database connection FAILED")
    yield
    # Shutdown
    logger.info("Shutting down...")


# App

app = FastAPI(
    title="Language Tutor Agent API",
    description="An agentic language tutor with persistent learner model and autonomous curriculum planning.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(session_router)
app.include_router(progress_router)
app.include_router(voice_router)


@app.get("/")
def root():
    return {
        "status": "running",
        "name": "Language Tutor Agent",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
    }


# Dev Runner

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)