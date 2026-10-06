"""Cloud entrypoint; one-time infrastructure bootstrap exports health only."""

import os

from fastapi import FastAPI


def create_app() -> FastAPI:
    if os.environ.get("CLOUD_BOOTSTRAP_ONLY") == "1":
        from app.api.routes.health import router

        bootstrap = FastAPI(title="Investment Tracker infrastructure bootstrap")
        bootstrap.include_router(router)
        return bootstrap

    from app.main import app

    return app


app = create_app()
