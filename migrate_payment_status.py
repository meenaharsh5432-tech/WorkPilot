from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("invoices")
    }

    if "payment_approval_status" in columns:
        print("Column already exists. No changes needed.")
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE invoices "
                "ADD COLUMN payment_approval_status "
                "VARCHAR(30) NOT NULL "
                "DEFAULT 'not_approved'"
            )
        )

    print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()