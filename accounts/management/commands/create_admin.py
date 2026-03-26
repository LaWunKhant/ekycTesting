from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Create a super admin user non-interactively or with prompts."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Admin email")
        parser.add_argument("--password", help="Admin password")
        parser.add_argument("--first-name", default="", help="Optional first name")
        parser.add_argument(
            "--role",
            default="super_admin",
            choices=["super_admin"],
            help="User role (fixed: super_admin).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update an existing user instead of failing.",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip()
        password = options.get("password") or ""
        first_name = (options.get("first_name") or "").strip()
        role = options["role"]
        force = bool(options.get("force"))

        if not email:
            email = input("Email: ").strip()
        if not password:
            password = getpass("Password: ")
            password_confirm = getpass("Password (again): ")
            if password != password_confirm:
                raise CommandError("Passwords do not match.")
        if not email:
            raise CommandError("Email is required.")
        if not password:
            raise CommandError("Password is required.")

        existing = User.objects.filter(email=email).first()
        if existing and not force:
            raise CommandError(
                "User already exists. Use --force to update password/role instead."
            )

        if existing:
            user = existing
            user.role = role
            user.tenant = None
            if first_name:
                user.first_name = first_name
            user.is_staff = True
            user.is_superuser = role == "super_admin"
            user.is_active = True
            user.set_password(password)
            user.save()
            action = "updated"
        else:
            create_kwargs = {
                "email": email,
                "password": password,
                "role": role,
                "is_staff": True,
            }
            if first_name:
                create_kwargs["first_name"] = first_name

            if role == "super_admin":
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    first_name=first_name,
                )
            else:
                user = User.objects.create_user(**create_kwargs)
            action = "created"

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin user {action}: {user.email} (role={user.role}, superuser={user.is_superuser})"
            )
        )
