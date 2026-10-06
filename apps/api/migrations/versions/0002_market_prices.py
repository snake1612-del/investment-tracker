"""Add manual market-price observations only (Decision 020)."""

import sqlalchemy as sa
from alembic import op

revision = "0002_market_prices"
down_revision = "0001_initial_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_price_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
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
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("price >= 0", name="price_nonnegative"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
        sa.UniqueConstraint("instrument_id", "effective_date"),
    )


def downgrade() -> None:
    op.drop_table("market_price_observations")
