"""Create the first administrator account.

Refuses to run once any user exists, so it cannot be used to plant a second
privileged account. The password is read from INITIAL_ADMIN_PASSWORD or a
prompt, never from a command-line argument in shell history.
"""

from __future__ import annotations

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.identity.models import User


class Command(BaseCommand):
    help = "Create the initial administrator account (refuses if any user exists)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", required=True)
        parser.add_argument(
            "--password",
            default=None,
            help="Prefer INITIAL_ADMIN_PASSWORD or the interactive prompt over this flag.",
        )

    def handle(self, *args, **options):
        if User.objects.exists():
            raise CommandError(
                "A user already exists. This command refuses to create another privileged "
                "account; use the administration process instead."
            )

        email = options["email"].strip().lower()
        password = (
            options["password"]
            or os.environ.get("INITIAL_ADMIN_PASSWORD")
            or getpass.getpass("Password: ")
        )

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        user = User.objects.create_superuser(
            email=email,
            full_name=options["full_name"],
            password=password,
        )
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Created administrator {user.email}. Password change required at first login."
            )
        )
