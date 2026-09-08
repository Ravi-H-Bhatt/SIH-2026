"""
Bootstrap the first admin account in Supabase.

Idempotent — safe to re-run. If the admin already exists but has no usable
password (e.g. it came from the legacy supabase_schema.sql seed, which used
Supabase Auth instead of a password hash) this resets it so you can log in.

Usage:
    cd backend && python3 init_admin.py
"""

from datetime import datetime, timezone

from app.core.config import settings

# Import the shared engine so the Supavisor pooler settings (NullPool,
# prepare_threshold=None) and the REQUIRE_SUPABASE guard all apply. Building a
# second engine from settings.DATABASE_URL here was a bug: that value is
# intentionally blank because the URL is derived from SUPABASE_DB_PASSWORD.
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.user import User

UNUSABLE_PASSWORD = "!locked:no-password-set"


def main() -> int:
    email = (settings.ADMIN_EMAIL or "").strip().lower()
    password = settings.ADMIN_PASSWORD
    if not email or not password:
        print("✗ Set ADMIN_EMAIL and ADMIN_PASSWORD in backend/.env first.")
        return 1

    print("📦 Ensuring ORM schema exists...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == email).first()

        if admin is None:
            admin = User(
                email=email,
                full_name=settings.ADMIN_FULL_NAME,
                hashed_password=hash_password(password),
                role="admin",
                is_active=True,
                is_approved=True,
                approved_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            db.commit()
            print(f"✓ Created admin: {email}")
        else:
            changed = []
            if admin.hashed_password in (None, "", UNUSABLE_PASSWORD):
                admin.hashed_password = hash_password(password)
                changed.append("password")
            if admin.role != "admin":
                admin.role = "admin"
                changed.append("role")
            if not admin.is_approved:
                admin.is_approved = True
                admin.approved_at = datetime.now(timezone.utc)
                changed.append("approval")
            if not admin.is_active:
                admin.is_active = True
                changed.append("active")

            if changed:
                db.commit()
                print(f"✓ Updated admin {email}: {', '.join(changed)}")
            else:
                print(f"· Admin already configured: {email}")

        print("\nAccounts in Supabase:")
        for user in db.query(User).order_by(User.created_at).all():
            usable = user.hashed_password not in (None, "", UNUSABLE_PASSWORD)
            state = "can log in" if usable else "LOCKED — no password set"
            print(f"  {user.email:<34} {user.role:<12} {state}")

        print("\n⚠️  Change this password after first login.")
        return 0

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"✗ {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
