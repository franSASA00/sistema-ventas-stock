"""insumo por producto

Revision ID: 9580a5939b22
Revises: 86b19c6e1d92
Create Date: 2026-08-10 23:03:25.439987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9580a5939b22'
down_revision: Union[str, Sequence[str], None] = '86b19c6e1d92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("productos") as batch_op:
        batch_op.add_column(sa.Column("insumo_id", sa.Integer(), sa.ForeignKey("productos.id"), nullable=True))
        batch_op.add_column(sa.Column("insumo_cantidad", sa.Integer(), nullable=True, server_default="1"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("productos") as batch_op:
        batch_op.drop_column("insumo_cantidad")
        batch_op.drop_column("insumo_id")
