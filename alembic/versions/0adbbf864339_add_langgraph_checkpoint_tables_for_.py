"""Add LangGraph checkpoint tables for PostgresSaver

Revision ID: 0adbbf864339
Revises: 93541014bf64
Create Date: 2026-10-20 11:16:07.469339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0adbbf864339'
down_revision: Union[str, Sequence[str], None] = '93541014bf64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create checkpoint_migrations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_migrations (
            v INTEGER PRIMARY KEY
        );
    """)
    
    # Create checkpoints table
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        );
    """)
    
    # Create checkpoint_blobs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_blobs (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL,
            version TEXT NOT NULL,
            type TEXT NOT NULL,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        );
    """)
    
    # Create checkpoint_writes table
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            blob BYTEA NOT NULL,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        );
    """)
    
    # Alter checkpoint_blobs blob column to be nullable
    op.execute("""
        ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP not null;
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);
    """)
    
    # Add task_path column to checkpoint_writes
    op.execute("""
        ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT '';
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS checkpoint_writes_thread_id_idx;")
    op.execute("DROP INDEX IF EXISTS checkpoint_blobs_thread_id_idx;")
    op.execute("DROP INDEX IF EXISTS checkpoints_thread_id_idx;")
    
    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS checkpoint_writes;")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs;")
    op.execute("DROP TABLE IF EXISTS checkpoints;")
    op.execute("DROP TABLE IF NOT EXISTS checkpoint_migrations;")
