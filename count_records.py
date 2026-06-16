from app import create_app, db
from app.models import User, Request, Approval, IssuedMaterial, Notification, AuditLog, InventorySnapshot, Material, ApprovalRule

app = create_app()
with app.app_context():
    print("User count (non-admin):", User.query.filter(User.role != 'admin').count())
    print("User count (admin):", User.query.filter_by(role='admin').count())
    print("Request count:", Request.query.count())
    print("Approval count:", Approval.query.count())
    print("IssuedMaterial count:", IssuedMaterial.query.count())
    print("Notification count:", Notification.query.count())
    print("AuditLog count:", AuditLog.query.count())
    print("InventorySnapshot count:", InventorySnapshot.query.count())
    print("Material count:", Material.query.count())
    print("ApprovalRule count:", ApprovalRule.query.count())
