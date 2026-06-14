"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2026-06-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(80), nullable=False),
        sa.Column('email', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('full_name', sa.String(150), nullable=False),
        sa.Column('department', sa.String(100)),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Inventory Snapshots table
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('total_items', sa.Integer(), server_default='0'),
        sa.Column('duplicate_items', sa.Integer(), server_default='0'),
        sa.Column('valid_items', sa.Integer(), server_default='0'),
        sa.Column('validation_summary', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_snapshots_snapshot_date', 'inventory_snapshots', ['snapshot_date'])

    # Materials table
    op.create_table(
        'materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), sa.ForeignKey('inventory_snapshots.id'), nullable=False),
        sa.Column('material_code', sa.String(100), nullable=False),
        sa.Column('material_description', sa.String(500), nullable=False),
        sa.Column('uom', sa.String(50)),
        sa.Column('unit_rate', sa.Numeric(15, 2), server_default='0'),
        sa.Column('available_stock', sa.Numeric(15, 3), server_default='0'),
        sa.Column('gl_code', sa.String(50)),
        sa.Column('cost_center', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_materials_snapshot_id', 'materials', ['snapshot_id'])
    op.create_index('ix_materials_material_code', 'materials', ['material_code'])

    # Approval Rules table
    op.create_table(
        'approval_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('min_amount', sa.Numeric(15, 2), server_default='0'),
        sa.Column('max_amount', sa.Numeric(15, 2)),
        sa.Column('required_levels', sa.Integer(), server_default='1'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Requests table
    op.create_table(
        'requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_number', sa.String(30), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), sa.ForeignKey('inventory_snapshots.id'), nullable=False),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('requester_name', sa.String(150), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column('material_code', sa.String(100)),
        sa.Column('material_description', sa.String(500)),
        sa.Column('uom', sa.String(50)),
        sa.Column('unit_rate', sa.Numeric(15, 2)),
        sa.Column('available_stock', sa.Numeric(15, 3)),
        sa.Column('quantity_required', sa.Numeric(15, 3), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('cost_center', sa.String(100)),
        sa.Column('gl_code', sa.String(50)),
        sa.Column('purpose', sa.Text()),
        sa.Column('status', sa.String(50), nullable=False, server_default='Pending Approval'),
        sa.Column('required_approval_levels', sa.Integer(), server_default='1'),
        sa.Column('current_approval_level', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_number'),
    )
    op.create_index('ix_requests_request_number', 'requests', ['request_number'])
    op.create_index('ix_requests_user_id', 'requests', ['user_id'])
    op.create_index('ix_requests_status', 'requests', ['status'])

    # Approvals table
    op.create_table(
        'approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('approver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approval_level', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('remarks', sa.Text()),
        sa.Column('actioned_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approvals_request_id', 'approvals', ['request_id'])

    # Notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id')),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('notification_type', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])

    # Issued Materials table
    op.create_table(
        'issued_materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('issued_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('issued_date', sa.Date(), nullable=False),
        sa.Column('issued_time', sa.Time(), nullable=False),
        sa.Column('remarks', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id'),
    )

    # Report Logs table
    op.create_table(
        'report_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(100)),
        sa.Column('report_date', sa.Date()),
        sa.Column('generated_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('filename', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(200), nullable=False),
        sa.Column('entity_type', sa.String(100)),
        sa.Column('entity_id', sa.Integer()),
        sa.Column('details', sa.Text()),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('audit_logs')
    op.drop_table('report_logs')
    op.drop_table('issued_materials')
    op.drop_table('notifications')
    op.drop_table('approvals')
    op.drop_table('requests')
    op.drop_table('approval_rules')
    op.drop_table('materials')
    op.drop_table('inventory_snapshots')
    op.drop_table('users')
