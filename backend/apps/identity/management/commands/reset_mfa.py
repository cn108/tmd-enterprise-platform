"""Reset a user's authenticator after an identity check by an administrator."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.identity.models import MfaChallenge, MfaDevice, User


class Command(BaseCommand):
    help = "Remove a user's MFA device, recovery codes and pending challenges."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Exact email address of the user to reset.")
        parser.add_argument(
            "--disable-requirement",
            action="store_true",
            help="Also clear the per-user mfa_required flag (development/recovery only).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"No user exists with email {email}.") from exc

        devices, _ = MfaDevice.objects.filter(user=user).delete()
        challenges, _ = MfaChallenge.objects.filter(user=user).delete()
        if options["disable_requirement"]:
            user.mfa_required = False
            user.save(update_fields=["mfa_required"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset MFA for {email}: {devices} device record(s) and "
                f"{challenges} pending challenge(s) removed."
            )
        )
