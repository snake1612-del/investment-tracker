"""Create the four canonical persistence tables.

Revision ID: 0001_initial_persistence
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'", name=op.f("ck_portfolios_base_currency_format")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolios")),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
    )
    op.create_table(
        "investment_accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("portfolio_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name=op.f("fk_investment_accounts_portfolio_id_portfolios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_accounts")),
    )
    op.create_index(
        op.f("ix_investment_accounts_portfolio_id"), "investment_accounts", ["portfolio_id"]
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=True),
        sa.Column("related_transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=28, scale=12), nullable=True),
        sa.Column("price", sa.Numeric(precision=28, scale=12), nullable=True),
        sa.Column("cash_amount", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'COUPON', 'FEE', 'TAX')",
            name=op.f("ck_transactions_type_values"),
        ),
        sa.CheckConstraint(
            "cash_amount >= 0", name=op.f("ck_transactions_cash_amount_nonnegative")
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name=op.f("ck_transactions_quantity_nonnegative")
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0", name=op.f("ck_transactions_price_nonnegative")
        ),
        sa.CheckConstraint(
            "currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_transactions_currency_code_format")
        ),
        sa.CheckConstraint(
            "related_transaction_id IS NULL OR related_transaction_id <> id",
            name=op.f("ck_transactions_no_direct_self_reference"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["investment_accounts.id"],
            name=op.f("fk_transactions_account_id_investment_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_transactions_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transactions_related_transaction_id_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(op.f("ix_transactions_account_id"), "transactions", ["account_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_investment_accounts_portfolio_id"), table_name="investment_accounts")
    op.drop_table("investment_accounts")
    op.drop_table("instruments")
    op.drop_table("portfolios")
