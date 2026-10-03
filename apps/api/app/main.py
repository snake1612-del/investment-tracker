from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes.accounts import router as accounts_router
from app.api.routes.cash import router as cash_router
from app.api.routes.health import router as health_router
from app.api.routes.instruments import router as instruments_router
from app.api.routes.money import router as money_router
from app.api.routes.portfolios import router as portfolios_router
from app.api.routes.transactions import router as transactions_router

app = FastAPI(title="Investment Tracker API")
app.include_router(health_router)
app.include_router(portfolios_router)
app.include_router(accounts_router)
app.include_router(instruments_router)
app.include_router(transactions_router)
app.include_router(cash_router)
app.include_router(money_router)
register_error_handlers(app)
