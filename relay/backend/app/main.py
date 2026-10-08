"""Builds the FastAPI app. Run with: uvicorn app.main:app"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME, FRONTEND_DIST_DIR
from app.database import Base, engine
from app.errors import register_error_handlers
from app.realtime import hub
from app.routers import agent, channels, instructions, users


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(engine)
    hub.start()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
register_error_handlers(app)
app.include_router(users.router)
app.include_router(channels.router)
app.include_router(agent.router)
app.include_router(instructions.router)


@app.get("/healthz", include_in_schema=False)
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# In production the backend also serves the built frontend, so everything runs as one process
# on one address. In development, Vite serves the frontend instead (see frontend/vite.config.ts).
if FRONTEND_DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def single_page_app(path: str) -> FileResponse:
        """Unknown paths get index.html so the React router can handle links like /c/<id>."""
        requested_file = (FRONTEND_DIST_DIR / path).resolve()
        if path and requested_file.is_file() and requested_file.is_relative_to(FRONTEND_DIST_DIR.resolve()):
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
