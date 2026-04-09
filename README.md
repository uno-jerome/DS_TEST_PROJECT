# Final Project ITC - Desktop E-Commerce

A desktop e-commerce system built with Python, CustomTkinter, and MySQL.

## What it does

- Buyer app: register/login (username, email, or phone), browse products, manage cart, checkout, and view order history.
- Admin app: manage inventory, view and update orders, and create sub-admin users.
- Launcher: start buyer, admin, or both apps from one command.

## Requirements

- Python 3.10+
- MySQL Server
- Python packages from requirements.txt

Install dependencies:

```bash
pip install -r requirements.txt
```

## Database setup

The app uses the schema from [Database.sql](Database.sql) and runtime migration checks in [database.py](database.py).

Default database name:

- itc_database_admin

You can override database connection values with environment variables:

- DB_HOST
- DB_PORT
- DB_USER
- DB_PASSWORD
- DB_NAME

Example .env values:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=itc_database_admin
```

## How to run

Buyer app (default):

```bash
python main.py
```

Admin app:

```bash
python main.py --app admin
```

Run both apps:

```bash
python main.py --app both
```

## Default admin login

- Username: admin
- Password: admin123

Change the default password after first login.

## Notes

## How to contribute

1. Create a feature branch.
2. Keep commits small and clear (for example: feat: add cart validation).
3. Test the buyer and admin flows before opening a pull request.
