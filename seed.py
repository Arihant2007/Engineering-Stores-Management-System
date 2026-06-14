"""
Seed script: populates the database with sample users, approval rules, and test inventory.
Run: flask seed-db
"""
from datetime import date, datetime
from app import create_app, db
from app.models import User, ApprovalRule, InventorySnapshot, Material


def seed():
    app = create_app()
    with app.app_context():
        print("Seeding database...")

        # ─── Approval Rules ─────────────────────────────────────────────
        if ApprovalRule.query.count() == 0:
            rules = [
                ApprovalRule(
                    name='Standard Approval (Up to Rs. 3000)',
                    min_amount=0,
                    max_amount=3000,
                    required_levels=1,
                    is_active=True
                ),
                ApprovalRule(
                    name='High Value Approval (Above Rs. 3000)',
                    min_amount=3000.01,
                    max_amount=None,
                    required_levels=2,
                    is_active=True
                ),
            ]
            db.session.bulk_save_objects(rules)
            db.session.commit()
            print("  Approval rules created.")

        # ─── Users ──────────────────────────────────────────────────────
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@engineering.com',
                'full_name': 'System Administrator',
                'department': 'IT',
                'role': 'admin',
                'password': 'Admin@123',
            },
            {
                'username': 'store.manager',
                'email': 'sunil.avirneni@gmail.com',
                'full_name': 'Store Manager',
                'department': 'Stores',
                'role': 'store_manager',
                'password': 'Store@123',
            },
            {
                'username': 'employee1',
                'email': 'employee1@engineering.com',
                'full_name': 'Priya Sharma',
                'department': 'Mechanical',
                'role': 'employee',
                'password': 'Emp@1234',
            },
            {
                'username': 'employee2',
                'email': 'employee2@engineering.com',
                'full_name': 'Arjun Patel',
                'department': 'Electrical',
                'role': 'employee',
                'password': 'Emp@1234',
            },
            {
                'username': 'employee3',
                'email': 'employee3@engineering.com',
                'full_name': 'Kavita Singh',
                'department': 'Civil',
                'role': 'employee',
                'password': 'Emp@1234',
            },
            {
                'username': 'approver.l1',
                'email': 'sunilraoavirneni@gmail.com',
                'full_name': 'Approver L1',
                'department': 'Engineering',
                'role': 'approver_l1',
                'password': 'Approver@123',
            },
            {
                'username': 'approver.l2',
                'email': 'approver2@engineering.com',
                'full_name': 'Dinesh Mehta',
                'department': 'Management',
                'role': 'approver_l2',
                'password': 'Approver@123',
            },
        ]

        created_count = 0
        updated_count = 0
        for ud in users_data:
            user = User.query.filter_by(username=ud['username']).first()
            if not user:
                user = User(
                    username=ud['username'],
                    email=ud['email'],
                    full_name=ud['full_name'],
                    department=ud['department'],
                    role=ud['role'],
                    is_active=True
                )
                user.set_password(ud['password'])
                db.session.add(user)
                created_count += 1
            else:
                user.email = ud['email']
                user.full_name = ud['full_name']
                user.department = ud['department']
                updated_count += 1

        db.session.commit()
        print(f"  {created_count} users created, {updated_count} users updated.")

        # ─── Sample Inventory Snapshot ───────────────────────────────────
        if InventorySnapshot.query.count() == 0:
            store_manager = User.query.filter_by(role='store_manager').first()
            if store_manager:
                snapshot = InventorySnapshot(
                    snapshot_date=date.today(),
                    filename='sample_inventory.xlsx',
                    uploaded_by=store_manager.id,
                    is_active=True,
                    total_items=20,
                    duplicate_items=0,
                    valid_items=20,
                    validation_summary='Sample inventory - no issues'
                )
                db.session.add(snapshot)
                db.session.flush()

                materials_data = [
                    ('MAT-001', 'MS Angle 50x50x5mm', 'KG', 85.50, 500.0, 'GL-5001', 'CC-MECH'),
                    ('MAT-002', 'GI Pipe 1 inch', 'MTR', 145.00, 200.0, 'GL-5002', 'CC-ELEC'),
                    ('MAT-003', 'Bearing 6205 ZZ', 'NOS', 320.00, 50.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-004', 'Allen Key Set (7pcs)', 'SET', 250.00, 30.0, 'GL-5001', 'CC-MECH'),
                    ('MAT-005', 'V-Belt A-45', 'NOS', 180.00, 100.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-006', 'Copper Wire 1.5 sqmm (100m)', 'ROLL', 1250.00, 25.0, 'GL-5002', 'CC-ELEC'),
                    ('MAT-007', 'MS Hex Bolt M12x50', 'KG', 75.00, 300.0, 'GL-5001', 'CC-MECH'),
                    ('MAT-008', 'Grease NLGI 2 (500g)', 'TIN', 95.00, 80.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-009', 'PVC Conduit 25mm (3m)', 'NOS', 55.00, 150.0, 'GL-5002', 'CC-ELEC'),
                    ('MAT-010', 'Cutting Wheel 4 inch', 'NOS', 45.00, 200.0, 'GL-5004', 'CC-WELDING'),
                    ('MAT-011', 'MS Sheet 3mm (1220x2440)', 'NOS', 4500.00, 20.0, 'GL-5001', 'CC-MECH'),
                    ('MAT-012', 'Hydraulic Oil 46 (20L)', 'CAN', 2800.00, 15.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-013', 'Cable Tie 300mm (100 pcs)', 'PKT', 120.00, 50.0, 'GL-5002', 'CC-ELEC'),
                    ('MAT-014', 'Welding Rod 3.15mm (5kg)', 'PKT', 550.00, 40.0, 'GL-5004', 'CC-WELDING'),
                    ('MAT-015', 'Safety Helmet (Blue)', 'NOS', 350.00, 30.0, 'GL-5005', 'CC-SAFETY'),
                    ('MAT-016', 'Cotton Waste', 'KG', 35.00, 500.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-017', 'Motor Oil SAE 30 (5L)', 'CAN', 650.00, 20.0, 'GL-5003', 'CC-MAINT'),
                    ('MAT-018', 'Hacksaw Blade 12 inch', 'NOS', 25.00, 200.0, 'GL-5001', 'CC-MECH'),
                    ('MAT-019', 'MCB 32A Single Pole', 'NOS', 285.00, 40.0, 'GL-5002', 'CC-ELEC'),
                    ('MAT-020', 'Teflon Tape (12mm x 12m)', 'NOS', 18.00, 500.0, 'GL-5001', 'CC-MECH'),
                ]

                for code, desc, uom, rate, stock, gl, cc in materials_data:
                    mat = Material(
                        snapshot_id=snapshot.id,
                        material_code=code,
                        material_description=desc,
                        uom=uom,
                        unit_rate=rate,
                        available_stock=stock,
                        gl_code=gl,
                        cost_center=cc
                    )
                    db.session.add(mat)

                db.session.commit()
                print("  Sample inventory snapshot with 20 materials created.")

        print("\n=== DATABASE SEEDED SUCCESSFULLY ===")
        print("\nTest Users:")
        print("  Username: admin          | Password: Admin@123   | Role: Administrator")
        print("  Username: store.manager  | Password: Store@123   | Role: Store Manager")
        print("  Username: employee1      | Password: Emp@1234    | Role: Employee")
        print("  Username: employee2      | Password: Emp@1234    | Role: Employee")
        print("  Username: employee3      | Password: Emp@1234    | Role: Employee")
        print("  Username: approver.l1   | Password: Approver@123 | Role: Approver L1")
        print("  Username: approver.l2   | Password: Approver@123 | Role: Approver L2")


if __name__ == '__main__':
    seed()
