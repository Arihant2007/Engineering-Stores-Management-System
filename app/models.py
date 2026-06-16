from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from app import db, login_manager


# ─────────────────────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    department = db.Column(db.String(100))
    role = db.Column(db.String(50), nullable=False)  # admin, store_manager, employee, approver_l1
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    requests = db.relationship('Request', backref='requester', lazy='dynamic', foreign_keys='Request.user_id')
    approvals = db.relationship('Approval', backref='approver', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    issued_materials = db.relationship('IssuedMaterial', backref='issued_by_user', lazy='dynamic')

    ROLES = {
        'admin': 'Administrator',
        'store_manager': 'Store Manager',
        'employee': 'Employee',
        'approver_l1': 'Approver',
    }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_password_token(token, expires_in=600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_in)['user_id']
        except:
            return None
        return User.query.get(user_id)

    @property
    def role_display(self):
        return self.ROLES.get(self.role, self.role)

    def is_admin(self):
        return self.role == 'admin'

    def is_store_manager(self):
        return self.role == 'store_manager'

    def is_employee(self):
        return self.role == 'employee'

    def is_approver_l1(self):
        return self.role == 'approver_l1'

    def is_approver(self):
        return self.role == 'approver_l1'

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────────────────────────────
#  INVENTORY SNAPSHOTS
# ─────────────────────────────────────────────────────────────
class InventorySnapshot(db.Model):
    __tablename__ = 'inventory_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    total_items = db.Column(db.Integer, default=0)
    duplicate_items = db.Column(db.Integer, default=0)
    valid_items = db.Column(db.Integer, default=0)
    validation_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    materials = db.relationship('Material', backref='snapshot', lazy='dynamic')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f'<InventorySnapshot {self.snapshot_date}>'


# ─────────────────────────────────────────────────────────────
#  MATERIALS
# ─────────────────────────────────────────────────────────────
class Material(db.Model):
    __tablename__ = 'materials'

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('inventory_snapshots.id'), nullable=False, index=True)
    material_code = db.Column(db.String(100), nullable=False, index=True)
    material_description = db.Column(db.String(500), nullable=False)
    uom = db.Column(db.String(50))
    unit_rate = db.Column(db.Numeric(15, 2), default=0)
    available_stock = db.Column(db.Numeric(15, 3), default=0)
    gl_code = db.Column(db.String(50))
    cost_center = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    request_items = db.relationship('Request', backref='material', lazy='dynamic', foreign_keys='Request.material_id')

    def __repr__(self):
        return f'<Material {self.material_code}>'


# ─────────────────────────────────────────────────────────────
#  APPROVAL RULES
# ─────────────────────────────────────────────────────────────
class ApprovalRule(db.Model):
    __tablename__ = 'approval_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    min_amount = db.Column(db.Numeric(15, 2), default=0)
    max_amount = db.Column(db.Numeric(15, 2))
    required_levels = db.Column(db.Integer, default=1)  # 1 or 2
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ApprovalRule {self.name}>'


# ─────────────────────────────────────────────────────────────
#  REQUESTS
# ─────────────────────────────────────────────────────────────
class Request(db.Model):
    __tablename__ = 'requests'

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('inventory_snapshots.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)

    requester_name = db.Column(db.String(150), nullable=False)
    requester_email = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(100), nullable=False)
    material_code = db.Column(db.String(100))
    material_description = db.Column(db.String(500))
    uom = db.Column(db.String(50))
    unit_rate = db.Column(db.Numeric(15, 2))
    available_stock = db.Column(db.Numeric(15, 3))
    quantity_required = db.Column(db.Numeric(15, 3), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    cost_center = db.Column(db.String(100))
    gl_code = db.Column(db.String(50))
    purpose = db.Column(db.Text)

    status = db.Column(db.String(50), default='Pending Approval', nullable=False, index=True)
    # Pending Approval | Approved | Rejected | Issued

    required_approval_levels = db.Column(db.Integer, default=1)
    current_approval_level = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    approvals = db.relationship('Approval', backref='request', lazy='dynamic', cascade='all, delete-orphan')
    issued_material = db.relationship('IssuedMaterial', backref='request', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='request', lazy='dynamic', cascade='all, delete-orphan')
    snapshot = db.relationship('InventorySnapshot', foreign_keys=[snapshot_id])

    def __repr__(self):
        return f'<Request {self.request_number}>'


# ─────────────────────────────────────────────────────────────
#  APPROVALS
# ─────────────────────────────────────────────────────────────
class Approval(db.Model):
    __tablename__ = 'approvals'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False, index=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approval_level = db.Column(db.Integer, nullable=False)  # 1 or 2
    action = db.Column(db.String(20), nullable=False)  # Approved | Rejected
    remarks = db.Column(db.Text)
    actioned_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Approval {self.id} - {self.action}>'


# ─────────────────────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50))  # request_created, approved, rejected, issued
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id}>'


# ─────────────────────────────────────────────────────────────
#  ISSUED MATERIALS
# ─────────────────────────────────────────────────────────────
class IssuedMaterial(db.Model):
    __tablename__ = 'issued_materials'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), unique=True, nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issued_date = db.Column(db.Date, nullable=False)
    issued_time = db.Column(db.Time, nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<IssuedMaterial {self.id}>'


# ─────────────────────────────────────────────────────────────
#  REPORT LOGS
# ─────────────────────────────────────────────────────────────
class ReportLog(db.Model):
    __tablename__ = 'report_logs'

    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(100))
    report_date = db.Column(db.Date)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    generator = db.relationship('User', foreign_keys=[generated_by])

    def __repr__(self):
        return f'<ReportLog {self.id}>'


# ─────────────────────────────────────────────────────────────
#  AUDIT LOGS
# ─────────────────────────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(200), nullable=False)
    entity_type = db.Column(db.String(100))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.id}>'
