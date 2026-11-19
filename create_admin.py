from getpass import getpass
from werkzeug.security import generate_password_hash
from database import get_db_connection, init_db


def create_admin():
    init_db()

    print("\nTAVENZIQ ENTERPRISES - ADMIN ACCOUNT SETUP")

    username = input("Enter administrator username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = getpass("Enter administrator password: ")
    confirm_password = getpass("Confirm administrator password: ")

    if len(password) < 10:
        print("Password must contain at least 10 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    password_hash = generate_password_hash(password)

    connection = get_db_connection()

    try:
        connection.execute(
            """
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
            """,
            (username, password_hash)
        )
        connection.commit()
        print("\nAdministrator account created successfully.")

    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            print("\nThat username already exists.")
        else:
            print("\nCould not create administrator:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
