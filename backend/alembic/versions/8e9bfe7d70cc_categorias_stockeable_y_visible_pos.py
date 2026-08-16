"""categorias stockeable y visible pos

Revision ID: 8e9bfe7d70cc
Revises: 9580a5939b22
Create Date: 2026-08-10 23:30:23.008193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e9bfe7d70cc'
down_revision: Union[str, Sequence[str], None] = '9580a5939b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("categorias") as batch_op:
        batch_op.add_column(sa.Column("stockeable", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("visible_pos", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("categorias") as batch_op:
        batch_op.drop_column("visible_pos")
        batch_op.drop_column("stockeable")
