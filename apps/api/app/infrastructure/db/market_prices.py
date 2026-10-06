"""Focused SQLAlchemy market-price persistence; the UoW owns commits."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.contracts import MarketPriceRecord
from app.application.use_cases import NotFound
from app.domain.market_prices import MarketPrice
from app.infrastructure.db.models import MarketPriceObservationModel as Model


def _record(model: Model) -> MarketPriceRecord:
    return MarketPriceRecord(
        model.id,
        model.instrument_id,
        model.price,
        model.currency_code,
        model.effective_date,
        model.created_at,
        model.updated_at,
    )


class SqlAlchemyMarketPriceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, fact: MarketPrice) -> MarketPriceRecord:
        model = Model(
            instrument_id=fact.instrument_id,
            price=fact.price,
            currency_code=fact.currency_code,
            effective_date=fact.effective_date,
        )
        self.session.add(model)
        self.session.flush()
        return _record(model)

    def get(self, instrument_id: int, observation_id: int) -> MarketPriceRecord | None:
        model = self.session.get(Model, observation_id)
        return _record(model) if model and model.instrument_id == instrument_id else None

    def list_for_instruments(self, instrument_ids: list[int]) -> list[MarketPriceRecord]:
        if not instrument_ids:
            return []
        return [
            _record(model)
            for model in self.session.scalars(
                select(Model)
                .where(Model.instrument_id.in_(instrument_ids))
                .order_by(Model.instrument_id, Model.effective_date.desc())
            )
        ]

    def update(self, observation_id: int, fact: MarketPrice) -> MarketPriceRecord:
        model = self.session.get(Model, observation_id)
        if model is None or model.instrument_id != fact.instrument_id:
            raise NotFound("Market-price observation not found")
        model.price = fact.price
        model.currency_code = fact.currency_code
        model.effective_date = fact.effective_date
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        return _record(model)

    def delete(self, observation_id: int) -> None:
        model = self.session.get(Model, observation_id)
        if model is None:
            raise NotFound("Market-price observation not found")
        self.session.delete(model)
        self.session.flush()
