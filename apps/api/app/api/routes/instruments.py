"""Minimal manual Instrument create/list API."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import InstrumentCreate, InstrumentRead
from app.application.use_cases import UowFactory, create_instrument, list_instruments
from app.bootstrap import get_uow_factory

router = APIRouter()


@router.post("/instruments", status_code=status.HTTP_201_CREATED, response_model=InstrumentRead)
def post_instrument(
    body: InstrumentCreate, factory: Annotated[UowFactory, Depends(get_uow_factory)]
) -> InstrumentRead:
    return InstrumentRead.from_record(create_instrument(factory, body.name))


@router.get("/instruments", response_model=list[InstrumentRead])
def get_instruments(
    factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> list[InstrumentRead]:
    return [InstrumentRead.from_record(record) for record in list_instruments(factory)]
