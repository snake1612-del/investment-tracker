"""Add immutable source-level CSV import receipts only (Decision 023)."""

import sqlalchemy as sa
from alembic import op

revision = "0003_csv_imports"
down_revision = "0002_market_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "csv_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("format_version", sa.String(), nullable=False),
        sa.Column("source_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["investment_accounts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("account_id", "format_version", "source_fingerprint"),
        sa.CheckConstraint("row_count > 0", name="row_count_positive"),
    )


def downgrade() -> None:
    op.drop_table("csv_imports")
