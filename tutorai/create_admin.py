"""One-time setup script: creates the single admin account.

Run this yourself, locally: python3 -m tutorai.create_admin

This is intentionally not part of the regular app and has no signup path
in the UI, so admin access stays limited to whoever runs this script.
Your password is read with getpass, so it's hidden as you type and never
appears in your shell history or in this conversation.
"""

import getpass

from tutorai import classes, db, users


def main() -> None:
    db.init_db()
    classes.ensure_default_classes()

    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")

    try:
        users.create_admin(username, password)
    except ValueError as error:
        print(f"Could not create admin: {error}")
        return

    print(f"Admin account '{username}' created.")


if __name__ == "__main__":
    main()
