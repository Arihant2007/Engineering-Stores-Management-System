import os
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'default'))

def fix_production_database():
    with app.app_context():
        try:
            # Add requester_email to requests if missing
            db.session.execute(text('ALTER TABLE requests ADD COLUMN requester_email VARCHAR(120);'))
            print("Successfully added requester_email to requests table.")
        except Exception as e:
            db.session.rollback()
            print(f"Note: requester_email column might already exist or failed: {e}")

        try:
            # Add employee_id to users if missing
            db.session.execute(text('ALTER TABLE users ADD COLUMN employee_id VARCHAR(50);'))
            db.session.execute(text('CREATE UNIQUE INDEX ix_users_employee_id ON users (employee_id);'))
            print("Successfully added employee_id to users table.")
        except Exception as e:
            db.session.rollback()
            print(f"Note: employee_id column might already exist or failed: {e}")
            
        db.session.commit()
        print("Database schema fix completed.")

if __name__ == '__main__':
    fix_production_database()
