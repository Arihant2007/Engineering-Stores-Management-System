# Engineering Stores Management System (ESMS)

A complete, production-ready **Engineering Stores Management System** that digitizes material requisition, approval workflows, and reporting.

---

## Features

- **Role-based access**: Admin, Store Manager, Employee, Approver L1, Approver L2
- **Daily inventory upload**: Excel file with duplicate removal and validation
- **Material requisition**: Employee creates requests with auto-filled material details
- **Multi-level approval**: Configurable amount-based routing (L1 only or L1+L2)
- **Material issuance**: Store Manager issues approved materials
- **12-sheet Excel reports**: Complete daily report download
- **Email notifications**: Gmail SMTP with in-app notifications
- **Health check endpoint**: `/health` returns `{"status": "healthy"}`

---

## Quick Start (Local)

### Prerequisites
- Python 3.10+
- PostgreSQL (local or Neon)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/engineering-stores.git
cd engineering-stores

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your DATABASE_URL and email settings

# 5. Initialize database
set FLASK_ENV=development
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 6. Seed sample data
flask seed-db

# 7. Run the application
python run.py
```

The app will be available at: **http://localhost:5000**

---

## Test Users

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@123` | Administrator |
| `store.manager` | `Store@123` | Store Manager |
| `employee1` | `Emp@1234` | Employee |
| `employee2` | `Emp@1234` | Employee |
| `approver.l1` | `Approver@123` | Approver Level 1 |
| `approver.l2` | `Approver@123` | Approver Level 2 |

---

## Workflow

1. **Store Manager** logs in and uploads daily inventory (Excel file)
2. **Employees** create material requisitions (material is auto-filled from inventory)
3. Requests are **routed to Approver L1** (all requests) → **Approver L2** (if amount > Rs. 3,000)
4. **Approvers** approve or reject with remarks
5. **Store Manager** issues approved materials
6. **Store Manager** downloads daily Excel report (12 sheets)

---

## Neon PostgreSQL Setup

1. Go to [neon.tech](https://neon.tech) and create a free project
2. Copy the connection string: `postgresql://user:pass@hostname/dbname?sslmode=require`
3. Add to your `.env` as `DATABASE_URL`

---

## GitHub Setup

```bash
git init
git add .
git commit -m "Initial commit - Engineering Stores Management System"
git branch -M main
git remote add origin https://github.com/yourusername/engineering-stores.git
git push -u origin main
```

---

## Render Deployment

### Step 1: Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up / Log in

### Step 2: Connect GitHub
1. Click **New** → **Web Service**
2. Connect your GitHub repo
3. Select the `engineering-stores` repository

### Step 3: Configure Service
- **Name**: `engineering-stores`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt && flask db upgrade && flask seed-db`
- **Start Command**: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

### Step 4: Set Environment Variables
In Render dashboard → Environment:
```
FLASK_ENV=production
SECRET_KEY=<generate a random 50-char string>
DATABASE_URL=<your Neon PostgreSQL connection string>
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
MAIL_SUPPRESS_SEND=false
```

### Step 5: Deploy
Click **Create Web Service** → Render will build and deploy automatically.

Your app will be available at: `https://engineering-stores.onrender.com`

---

## Gmail SMTP Setup

1. Enable 2-Factor Authentication on your Gmail account
2. Go to Google Account → Security → **App Passwords**
3. Generate an App Password for "Mail"
4. Use this 16-character password as `MAIL_PASSWORD`

---

## Keeping Render Free Tier Active

Render free tier spins down after 15 minutes of inactivity. To keep it active:

### Option 1: UptimeRobot (Free)
1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create a free account
3. Add HTTP monitor: `https://engineering-stores.onrender.com/health`
4. Set interval: 5 minutes

### Option 2: Cron-job.org (Free)
1. Go to [cron-job.org](https://cron-job.org)
2. Create a job to GET `https://engineering-stores.onrender.com/health`
3. Schedule: every 10 minutes

The `/health` endpoint returns: `{"status": "healthy"}`

---

## Project Structure

```
engineering-stores/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # SQLAlchemy models
│   ├── utils.py             # Template filters
│   ├── notifications.py     # Email + in-app notifications
│   ├── auth/                # Authentication blueprint
│   ├── admin/               # Admin blueprint
│   ├── store/               # Store Manager blueprint
│   ├── employee/            # Employee blueprint
│   ├── approver/            # Approver blueprint
│   ├── reports/             # Reports blueprint
│   ├── main/                # Main/dashboard blueprint
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JavaScript
├── migrations/              # Flask-Migrate / Alembic
├── config.py                # Configuration classes
├── run.py                   # Application entry point
├── seed.py                  # Database seeder
├── create_sample_inventory.py  # Create test inventory file
├── requirements.txt
├── Procfile
├── render.yaml
├── .env.example
└── .gitignore
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (returns `{"status": "healthy"}`) |
| `/store/api/materials` | GET | Material search API (JSON) |
| `/store/api/material/<id>` | GET | Single material details (JSON) |
| `/api/notifications/count` | GET | Unread notification count (JSON) |

---

## Database Tables

- `users` - System users with roles
- `inventory_snapshots` - Daily inventory upload history
- `materials` - Individual materials per snapshot
- `approval_rules` - Configurable approval routing rules
- `requests` - Material requisitions
- `approvals` - Approval/rejection records
- `notifications` - In-app notifications
- `issued_materials` - Issuance records
- `report_logs` - Report download history
- `audit_logs` - Complete system audit trail

---

## Security Features

- Password hashing (Werkzeug)
- CSRF protection (Flask-WTF)
- SQL injection protection (SQLAlchemy ORM)
- Session security (Flask-Login)
- Input validation
- Role-based access control
