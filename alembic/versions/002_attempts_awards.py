"""Attempts, answers, user correctness, and awards tables

Revision ID: 002_attempts_awards
Revises: 001_initial_schema
Create Date: 2025-09-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_attempts_awards'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # attempt table
    op.create_table(
        'attempt',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('quiz_id', sa.UUID(), nullable=False),
        sa.Column('locale', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_attempt_user_quiz', 'attempt', ['user_id', 'quiz_id', 'started_at'], unique=False)
    op.create_index('idx_attempt_quiz_time', 'attempt', ['quiz_id', 'started_at'], unique=False)

    # attempt_answer table
    op.create_table(
        'attempt_answer',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('attempt_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['attempt_id'], ['attempt.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attempt_id', 'question_id')
    )
    op.create_index('idx_ans_attempt', 'attempt_answer', ['attempt_id'], unique=False)
    op.create_index('idx_ans_user_q', 'attempt_answer', ['question_id', 'is_correct'], unique=False)

    # user_question_state
    op.create_table(
        'user_question_state',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('first_correct_attempt_id', sa.UUID(), nullable=False),
        sa.Column('first_correct_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['first_correct_attempt_id'], ['attempt.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'question_id')
    )

    # balance_account
    op.create_table(
        'balance_account',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('current_balance', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )

    # balance_ledger
    op.create_table(
        'balance_ledger',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ledger_user_time', 'balance_ledger', ['user_id', 'created_at'], unique=False)

    # quiz_award
    op.create_table(
        'quiz_award',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('quiz_id', sa.UUID(), nullable=False),
        sa.Column('attempt_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'quiz_id', 'attempt_id')
    )


def downgrade() -> None:
    op.drop_table('quiz_award')
    op.drop_index('idx_ledger_user_time', table_name='balance_ledger')
    op.drop_table('balance_ledger')
    op.drop_table('balance_account')
    op.drop_table('user_question_state')
    op.drop_index('idx_ans_user_q', table_name='attempt_answer')
    op.drop_index('idx_ans_attempt', table_name='attempt_answer')
    op.drop_table('attempt_answer')
    op.drop_index('idx_attempt_quiz_time', table_name='attempt')
    op.drop_index('idx_attempt_user_quiz', table_name='attempt')
    op.drop_table('attempt') 