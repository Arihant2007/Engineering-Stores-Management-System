import os
from app import create_app, db
from app.models import User, Request, Approval, IssuedMaterial, Notification, AuditLog, InventorySnapshot, Material, ReportLog, ApprovalRule

app = create_app(os.environ.get('FLASK_ENV', 'development'))

with app.app_context():
    deleted_counts = {
        'Notification': 0,
        'AuditLog': 0,
        'ReportLog': 0,
        'Approval': 0,
        'IssuedMaterial': 0,
        'Request': 0,
        'Material': 0,
        'InventorySnapshot': 0,
        'User': 0
    }

    print("Starting ORM-safe database cleanup...")

    # 1. Standalone / deeply nested children
    for notif in Notification.query.all():
        db.session.delete(notif)
        deleted_counts['Notification'] += 1
        
    for log in AuditLog.query.all():
        db.session.delete(log)
        deleted_counts['AuditLog'] += 1
        
    for rlog in ReportLog.query.all():
        db.session.delete(rlog)
        deleted_counts['ReportLog'] += 1

    # 2. Request-dependent objects
    for approval in Approval.query.all():
        db.session.delete(approval)
        deleted_counts['Approval'] += 1
        
    for issued in IssuedMaterial.query.all():
        db.session.delete(issued)
        deleted_counts['IssuedMaterial'] += 1

    # 3. Requests
    for req in Request.query.all():
        db.session.delete(req)
        deleted_counts['Request'] += 1

    # 4. Materials
    for mat in Material.query.all():
        db.session.delete(mat)
        deleted_counts['Material'] += 1

    # 5. Inventory Snapshots
    for snap in InventorySnapshot.query.all():
        db.session.delete(snap)
        deleted_counts['InventorySnapshot'] += 1

    # 6. Non-Admin Users
    for user in User.query.filter(User.role != 'admin').all():
        db.session.delete(user)
        deleted_counts['User'] += 1

    # Commit the transaction
    db.session.commit()

    print("\nCleanup Summary:")
    for model, count in deleted_counts.items():
        print(f"Removed {count} {model}(s)")
    
    # Verification
    admin_count = User.query.filter_by(role='admin').count()
    rule_count = ApprovalRule.query.count()
    print(f"\nVerification:")
    print(f"Admin Accounts Remaining: {admin_count}")
    print(f"ApprovalRules Remaining: {rule_count}")
