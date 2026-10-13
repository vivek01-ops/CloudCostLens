"""Secure first-owner bootstrap.

Creates the initial organization and owner user. There is NO default administrator:
the operator supplies the owner email and a strong password interactively (or via the
BOOTSTRAP_OWNER_PASSWORD environment variable in non-interactive deployments).

Usage:
    python -m scripts.bootstrap_owner
"""

from __future__ import annotations

import argparse
import getpass
import os

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError  # noqa: F401  (re-exported API)
from core.config import get_settings
from core.db.session import get_session
from core.logging import configure_logging, get_logger
from core.models import Membership, Organization, User
from core.models.enums import Role

log = get_logger("scripts.bootstrap_owner")


def _read_password(interactive: bool, env_value: str | None) -> str:
    if env_value:
        return env_value
    if not interactive:
        raise SystemExit(
            "BOOTSTRAP_OWNER_PASSWORD must be provided when running non-interactively."
        )
    password = getpass.getpass("Owner password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    return password


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    parser = argparse.ArgumentParser(description="Create the initial CloudCostLens owner.")
    parser.add_argument("--org-name", default="My Organization")
    parser.add_argument("--org-slug", default="my-org")
    parser.add_argument("--email", required=True, dest="email")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Read password from BOOTSTRAP_OWNER_PASSWORD.",
    )
    args = parser.parse_args(argv)

    password = _read_password(args.non_interactive, os.getenv("BOOTSTRAP_OWNER_PASSWORD"))

    hasher = PasswordHasher()
    password_hash = hasher.hash(password)

    with get_session() as db:
        if db.query(User).filter(User.email == args.email).first():
            raise SystemExit(f"User {args.email} already exists.")

        org = db.query(Organization).filter(Organization.slug == args.org_slug).first()
        if org is None:
            org = Organization(name=args.org_name, slug=args.org_slug)
            db.add(org)
            db.flush()
            log.info("organization_created", slug=org.slug)

        user = User(
            email=args.email,
            display_name=args.email,
            password_hash=password_hash,
            is_active=True,
        )
        db.add(user)
        db.flush()

        db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.OWNER))
        log.info("owner_created", email=args.email, organization=org.slug, role=Role.OWNER.value)

    print(f"Owner created: {args.email} (organization '{args.org_slug}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())