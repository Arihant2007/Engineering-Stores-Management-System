import os
import sys
from sqlalchemy import inspect
from flask_migrate import upgrade, stamp
from app import create_app, db

def check_and_migrate():
    # Create the Flask app context
    app = create_app(os.environ.get('FLASK_ENV', 'production'))
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Check if the base tables exist
        tables = inspector.get_table_names()
        has_base_tables = 'users' in tables
        
        # Check if alembic_version exists
        has_alembic = 'alembic_version' in tables
        
        try:
            # If tables exist but no alembic history, stamp the initial migration
            if has_base_tables and not has_alembic:
                print("Detected existing base tables without Alembic history.")
                print("Stamping 001_initial...")
                stamp(revision='001_initial')
            
            # Run the normal upgrade process
            print("Running database migrations...")
            upgrade()
            print("Database migrations applied successfully.")
            return True
            
        except Exception as e:
            print(f"Migration failed: {e}")
            return False

if __name__ == '__main__':
    success = check_and_migrate()
    if not success:
        sys.exit(1)
