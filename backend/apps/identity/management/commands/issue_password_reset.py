"""Issue a single-use password reset token for an existing user.

The raw token is printed once and never stored; only its hash is kept. Deliver
it out-of-band (in person or by a channel the user controls) and do not paste it
into chat, email threads or ticket comments.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.identity.models import PasswordResetToken, User


class Command(BaseCommand):
    help = "Issue a single-use password reset token for a user."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--issued-by", default=None, help="Email of the administrator issuing it."
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user is None:
            raise CommandError(f"No user with email {email}.")
        if not user.is_active:
            raise CommandError("This account is disabled; re-enable it first.")

        issued_by = None
        if options["issued_by"]:
            issued_by = User.objects.filter(email=options["issued_by"].strip().lower()).first()

        token, raw_token = PasswordResetToken.issue(user, issued_by=issued_by)
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset token for {user.email} (valid until {token.expires_at:%Y-%m-%d %H:%M %Z}):"
            )
        )
        self.stdout.write(raw_token)
        self.stdout.write("Deliver this out-of-band. It cannot be retrieved again.")
