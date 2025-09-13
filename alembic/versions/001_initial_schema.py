"""Initial database schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-09-12 11:51:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create media_asset table
    op.create_table('media_asset',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('s3_bucket', sa.String(), nullable=False),
    sa.Column('s3_key', sa.String(), nullable=False),
    sa.Column('mime', sa.String(), nullable=False),
    sa.Column('sha256', sa.LargeBinary(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('s3_bucket', 's3_key')
    )

    # Create quiz table
    op.create_table('quiz',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('status', postgresql.ENUM('draft', 'published', 'archived', name='quizstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )

    # Create question table
    op.create_table('question',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('quiz_id', sa.UUID(), nullable=False),
    sa.Column('qtype', postgresql.ENUM('single_choice', 'multi_choice', 'fill_gap', 'matching', name='questiontype'), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quiz_id', 'display_order')
    )
    op.create_index('idx_question_quiz_order', 'question', ['quiz_id', 'display_order'], unique=False)

    # Create media_asset_i18n table
    op.create_table('media_asset_i18n',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('locale', sa.String(), nullable=False),
    sa.Column('alt_text', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['media_asset.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('asset_id', 'locale')
    )

    # Create quiz_i18n table
    op.create_table('quiz_i18n',
    sa.Column('quiz_id', sa.UUID(), nullable=False),
    sa.Column('locale', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('quiz_id', 'locale')
    )

    # Create quiz_stats table
    op.create_table('quiz_stats',
    sa.Column('quiz_id', sa.UUID(), nullable=False),
    sa.Column('total_submissions', sa.Integer(), nullable=False),
    sa.Column('avg_score', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id'], ),
    sa.PrimaryKeyConstraint('quiz_id')
    )

    # Create choice_option table
    op.create_table('choice_option',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('question_id', 'display_order')
    )
    op.create_index('idx_choice_question', 'choice_option', ['question_id'], unique=False)

    # Create fill_gap table
    op.create_table('fill_gap',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('gap_index', sa.Integer(), nullable=False),
    sa.Column('case_sensitive', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('question_id', 'gap_index')
    )

    # Create matching_pair table
    op.create_table('matching_pair',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('left_kind', postgresql.ENUM('text', 'image', name='sidekind'), nullable=False),
    sa.Column('left_text', sa.Text(), nullable=True),
    sa.Column('left_asset_id', sa.UUID(), nullable=True),
    sa.Column('right_kind', postgresql.ENUM('text', 'image', name='sidekind'), nullable=False),
    sa.Column('right_text', sa.Text(), nullable=True),
    sa.Column('right_asset_id', sa.UUID(), nullable=True),
    sa.CheckConstraint("(left_kind='text' AND left_text IS NOT NULL) OR (left_kind='image' AND left_asset_id IS NOT NULL)"),
    sa.CheckConstraint("(right_kind='text' AND right_text IS NOT NULL) OR (right_kind='image' AND right_asset_id IS NOT NULL)"),
    sa.ForeignKeyConstraint(['left_asset_id'], ['media_asset.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['right_asset_id'], ['media_asset.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_match_question', 'matching_pair', ['question_id'], unique=False)

    # Create question_i18n table
    op.create_table('question_i18n',
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('locale', sa.String(), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('question_id', 'locale')
    )

    # Create question_stats table
    op.create_table('question_stats',
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('total_attempts', sa.Integer(), nullable=False),
    sa.Column('total_correct', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
    sa.PrimaryKeyConstraint('question_id')
    )

    # Create choice_option_i18n table
    op.create_table('choice_option_i18n',
    sa.Column('option_id', sa.UUID(), nullable=False),
    sa.Column('locale', sa.String(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['choice_option.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('option_id', 'locale')
    )

    # Create fill_gap_answer table
    op.create_table('fill_gap_answer',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('gap_id', sa.UUID(), nullable=False),
    sa.Column('accepted_value', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['gap_id'], ['fill_gap.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_fga_gap', 'fill_gap_answer', ['gap_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_fga_gap', table_name='fill_gap_answer')
    op.drop_table('fill_gap_answer')
    op.drop_table('choice_option_i18n')
    op.drop_table('question_stats')
    op.drop_table('question_i18n')
    op.drop_index('idx_match_question', table_name='matching_pair')
    op.drop_table('matching_pair')
    op.drop_table('fill_gap')
    op.drop_index('idx_choice_question', table_name='choice_option')
    op.drop_table('choice_option')
    op.drop_table('quiz_stats')
    op.drop_table('quiz_i18n')
    op.drop_table('media_asset_i18n')
    op.drop_index('idx_question_quiz_order', table_name='question')
    op.drop_table('question')
    op.drop_table('quiz')
    op.drop_table('media_asset') 