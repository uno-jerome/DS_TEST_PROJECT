# Final Project ITC - Desktop E-Commerce

A simple desktop e-commerce system built with Python, CustomTkinter, and MySQL.

## What this project does

- Admin app: manage inventory, update order status, manage admin accounts
- Shop app: customer login/register, browse products, cart, checkout, order history
- Database bootstrap: creates required tables on startup

## Requirements

- Python 3.10+
- MySQL Server
- pip (Python package installer)

## Setup

1. Clone or download this project.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create the database in MySQL (one time):

```sql
CREATE DATABASE itc_database_admin;
```

5. Open `database.py` and update `DB_CONFIG` with your MySQL username/password if needed.

## Run

- Start admin app:

```bash
python admin_app.py
```

- Start shop app:

```bash
python buyer_app.py
```

## Default admin login

- Username: `admin`
- Password: `admin123`

Change this immediately after first login.

## Notes

- This repo uses `.gitignore` so local/runtime files (venv, receipts, cache, exports, local state, secrets) are not committed.
- If you already staged files before adding `.gitignore`, unstage/remove them from Git index first.
