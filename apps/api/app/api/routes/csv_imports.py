"""Raw CSV transport boundary; no data access or financial calculations."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.application.csv_imports import Diagnostic, InvalidCsv, import_csv
from app.application.use_cases import UowFactory
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.post("/accounts/{account_id}/transaction-imports/csv")
async def post_csv(
    account_id: int, request: Request, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    parts = [part.strip().lower() for part in content_type.split(";")]
    try:
        if parts != ["text/csv", "charset=utf-8"]:
            raise InvalidCsv(
                [
                    Diagnostic(
                        None,
                        None,
                        "file",
                        "INVALID_CSV",
                        "Use Content-Type: text/csv; charset=utf-8",
                    )
                ]
            )
        payload = await request.body()
        result = await run_in_threadpool(import_csv, factory, account_id, payload)
    except InvalidCsv as exc:
        return JSONResponse(
            status_code=422, content={"detail": [asdict(item) for item in exc.diagnostics]}
        )
    receipt = result.receipt
    return JSONResponse(
        status_code=201 if result.status == "IMPORTED" else 200,
        content={
            "import_id": receipt.id,
            "status": result.status,
            "format_version": receipt.format_version,
            "source_fingerprint": receipt.source_fingerprint,
            "row_count": receipt.row_count,
        },
    )
