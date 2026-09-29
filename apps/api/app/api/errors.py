"""Map expected application/domain outcomes to HTTP statuses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.use_cases import InvalidInput, NotFound, PersistenceConflict
from app.domain.instruments import InvalidInstrument
from app.domain.transactions import InvalidTransaction


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFound)
    async def not_found(_request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidInput)
    async def invalid_input(_request: Request, exc: InvalidInput) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransaction)
    async def invalid_transaction(_request: Request, exc: InvalidTransaction) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidInstrument)
    async def invalid_instrument(_request: Request, exc: InvalidInstrument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PersistenceConflict)
    async def conflict(_request: Request, _exc: PersistenceConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Persistence conflict"})
