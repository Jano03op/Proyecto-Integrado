# SGR (Sistema de Gestión y Rendición)

SGR is a Django-based municipal management system for municipal delegations, collective agenda commitments, operational metrics, and staff accountability.

---

## Architecture Overview

The system is organized into four core domain modules backed by a 9-entity relational MySQL/SQLite schema:

- **`cuentas`**: Authentication, role-based session handling, user profiles (`StaffProfile`), and dashboard.
- **`organizacion`**: Territorial delegations (`Delegation`), global catalog positions (`Position`), and delegation lifecycle management.
- **`agenda`**: Collective agenda commitments (`Commitment`) and chronological append-only audit trail (`CommitmentEvent`).
- **`indicadores`**: Periodic reporting intervals (`Period`), catalog metrics (`MetricItem`), and individual staff targets (`StaffTarget`).

---

## Requirements

- Python 3.12+
- MySQL 8.x / MariaDB (or SQLite for local lightweight testing)
- C/C++ compiler or prebuilt binary wheels for `mysqlclient`

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd Proyecto-Integrado
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Linux / macOS:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

The project uses environment variables for security and deployment isolation. See `.env.example` for reference.

For local development with MySQL (e.g., WampServer on port 3306):

```powershell
$env:SECRET_KEY="your-secret-key-here"
$env:DEBUG="True"
$env:ALLOWED_HOSTS="localhost,127.0.0.1"
$env:DB_BACKEND="mysql"
$env:DB_NAME="sgr_db"
$env:DB_USER="root"
$env:DB_PASSWORD=""
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
```

For lightweight local development with SQLite:

```powershell
$env:SECRET_KEY="your-secret-key-here"
$env:DEBUG="True"
$env:ALLOWED_HOSTS="localhost,127.0.0.1"
$env:DB_BACKEND="sqlite"
```

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Import initial data (Optional)

If a legacy `datosarray.json` is available, run the data reconciliation and import command:

```bash
# Dry run verification:
python manage.py import_sgr_data --dry-run

# Commit import:
python manage.py import_sgr_data
```

To create an administrator manually:

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver 127.0.0.1:8000
```

Navigate to:
- Portal: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/cuentas/login/`
- Admin panel: `http://127.0.0.1:8000/admin/`

---

## Running Automated Tests

Run the full automated test suite across all four applications:

```bash
python manage.py test organizacion cuentas indicadores agenda
```
