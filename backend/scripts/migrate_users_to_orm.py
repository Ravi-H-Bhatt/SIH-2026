#!/usr/bin/env python3
"""
Reconcile the Supabase `users` table with the SQLAlchemy User model.

WHY THIS EXISTS
---------------
This project accumulated two competing schemas:

  * supabase_schema.sql — a 20-table design (screenings, documents, mrz_records,
    ...) with hashed PII, RLS policies, and a native `user_role` enum using
    UPPERCASE labels. It was applied to the Supabase project at some point.

  * app/models/*.py — the 7-table SQLAlchemy schema that every API route, the
    screening pipeline, and the frontend actually use. Roles here are lowercase
    varchar ("officer", "supervisor", "admin", "investigator").

`Base.metadata.create_all()` creates missing tables but never alters existing
ones, so the pre-existing `users` table silently lacked `hashed_password`,
`is_approved`, `approved_by` and `approved_at`. Login would fail with
UndefinedColumn the first time anyone authenticated.

WHAT THIS DOES
--------------
Makes the ORM authoritative for `users`, in place and idempotently:

  1. Converts `role` from the `user_role` enum to VARCHAR(50), lowercasing
     existing labels so ADMIN -> admin.
  2. Adds the four missing ORM columns.
  3. Backfills `hashed_password` on legacy rows with a deliberately unusable
     value, then enforces NOT NULL. Those accounts cannot log in until an admin
     sets a real password — that is intentional, not an oversight.
  4. Creates the 6 remaining ORM tables via create_all().

WHAT THIS DOES *NOT* DO
-----------------------
Nothing is dropped. The 19 legacy tables (screenings, stations, watchlist_entries,
...) and the `user_role` enum are left exactly as they are. They are unused by
the running app but may still hold seed data you want, and legacy foreign keys
point at `users`.

Safe to run repeatedly.

Usage:
    cd backend && python3 scripts/migrate_users_to_orm.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.core.config import settings  # noqa: E402

OK = "\033[92m✓\033[0m"
SKIP = "\033[90m·\033[0m"
BAD = "\033[91m✗\033[0m"

# bcrypt-shaped but not a valid hash of anything, so verify() always fails.
UNUSABLE_PASSWORD = "!locked:no-password-set"

ORM_COLUMNS = {
    "hashed_password": "TEXT",
    "is_approved": "BOOLEAN NOT NULL DEFAULT false",
    "approved_by": "UUID",
    "approved_at": "TIMESTAMPTZ",
}


def _backup_policies(conn, dependent: list) -> None:
    """
    Dump the full CREATE POLICY statements for policies we are about to drop.

    This project has no version control, so a dropped policy would otherwise be
    unrecoverable. The generated file is replayable SQL.
    """
    wanted = {(t, p) for t, p in dependent}
    rows = conn.execute(
        text(
            """
            select tablename, policyname, permissive, roles, cmd, qual, with_check
            from pg_policies
            where schemaname = 'public'
            order by tablename, policyname
            """
        )
    ).all()

    lines = [
        "-- Legacy RLS policies dropped by scripts/migrate_users_to_orm.py",
        "-- Replay this file to restore them (requires users.role to be user_role enum again).",
        "",
    ]
    for table, policy, permissive, roles, cmd, qual, with_check in rows:
        if (table, policy) not in wanted:
            continue
        role_list = ", ".join(roles) if roles else "public"
        stmt = [f'CREATE POLICY "{policy}" ON public."{table}"']
        stmt.append(f"  AS {permissive}")
        stmt.append(f"  FOR {cmd}")
        stmt.append(f"  TO {role_list}")
        if qual:
            stmt.append(f"  USING ({qual})")
        if with_check:
            stmt.append(f"  WITH CHECK ({with_check})")
        lines.append("\n".join(stmt) + ";\n")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dropped_policies.sql")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    url = settings.resolved_database_url()
    if not url.startswith("postgresql"):
        print(f"{BAD} Not connected to Supabase Postgres. Run scripts/verify_supabase.py first.")
        return 1

    engine = create_engine(url, connect_args={"connect_timeout": 15})
    print("\n\033[1mMIGRATE users -> ORM SCHEMA\033[0m")
    print("─" * 66)

    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("users")}

        # ── 1. role: user_role enum -> varchar(50), lowercased ──────────────
        udt = conn.execute(
            text(
                "select udt_name from information_schema.columns "
                "where table_schema='public' and table_name='users' and column_name='role'"
            )
        ).scalar_one_or_none()

        if udt == "user_role":
            # Postgres refuses to alter a column that any RLS policy references.
            # The legacy policies are all built on Supabase Auth (auth.uid()) and
            # the unused `screenings` tables; this app authenticates with its own
            # JWTs and connects as `postgres`, which bypasses RLS entirely. So
            # they block the migration without protecting anything we use.
            #
            # RLS itself stays ENABLED on those tables. With the policies gone
            # and RLS on, Postgres default-denies anon/authenticated — a tighter
            # posture than before, not a looser one.
            dependent = conn.execute(
                text(
                    """
                    select tablename, policyname
                    from pg_policies
                    where schemaname = 'public'
                      and (coalesce(qual, '') || coalesce(with_check, '')) like '%role%'
                    order by tablename, policyname
                    """
                )
            ).all()

            if dependent:
                _backup_policies(conn, dependent)
                for table, policy in dependent:
                    conn.execute(text(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"'))
                print(f"{OK} dropped {len(dependent)} legacy RLS policy/policies "
                      f"(backed up to scripts/dropped_policies.sql)")

            # The enum-typed DEFAULT must go before the type can change.
            conn.execute(text("ALTER TABLE users ALTER COLUMN role DROP DEFAULT"))
            conn.execute(
                text(
                    "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) "
                    "USING lower(role::text)"
                )
            )
            conn.execute(text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'officer'"))
            print(f"{OK} role: user_role enum -> VARCHAR(50), labels lowercased")
        else:
            conn.execute(text("UPDATE users SET role = lower(role) WHERE role <> lower(role)"))
            print(f"{SKIP} role already VARCHAR (udt={udt}); ensured lowercase")

        # ── 2. add the missing ORM columns ──────────────────────────────────
        for name, ddl in ORM_COLUMNS.items():
            if name in existing:
                print(f"{SKIP} column '{name}' already present")
            else:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
                print(f"{OK} added column '{name}' {ddl}")

        # ── 3. backfill + enforce NOT NULL on hashed_password ───────────────
        locked = conn.execute(
            text(
                "UPDATE users SET hashed_password = :pw "
                "WHERE hashed_password IS NULL OR hashed_password = ''"
            ),
            {"pw": UNUSABLE_PASSWORD},
        ).rowcount
        if locked:
            print(f"{OK} locked {locked} legacy row(s) with an unusable password")

        conn.execute(text("ALTER TABLE users ALTER COLUMN hashed_password SET NOT NULL"))
        print(f"{OK} hashed_password NOT NULL enforced")

        # Existing seed admins were created before the approval flow existed.
        promoted = conn.execute(
            text("UPDATE users SET is_approved = true WHERE role = 'admin' AND is_approved = false")
        ).rowcount
        if promoted:
            print(f"{OK} marked {promoted} existing admin(s) approved")

    # ── 4. create the remaining ORM tables ──────────────────────────────────
    print()
    from app.core.database import Base  # noqa: E402  (imports models via __init__)
    import app.models  # noqa: F401,E402  ensure every model is registered

    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())

    created = sorted(after - before)
    if created:
        print(f"{OK} created ORM tables: {', '.join(created)}")
    else:
        print(f"{SKIP} all ORM tables already existed")

    # ── 5. default-deny RLS on the ORM tables ───────────────────────────────
    # create_all() leaves RLS off, which means anyone holding the *public* anon
    # key could read passport data straight out of the REST API. The backend
    # connects as `postgres` and bypasses RLS, so enabling it with no policies
    # costs us nothing and closes that hole.
    orm_tables = [
        "users", "scan_records", "extracted_data",
        "forgery_results", "face_results", "risk_scores", "audit_logs",
    ]
    with engine.begin() as conn:
        secured = []
        for table in orm_tables:
            enabled = conn.execute(
                text(
                    "select relrowsecurity from pg_class "
                    "where relname = :t and relnamespace = 'public'::regnamespace"
                ),
                {"t": table},
            ).scalar_one_or_none()
            if enabled is False:
                conn.execute(text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
                secured.append(table)
        if secured:
            print(f"{OK} enabled default-deny RLS on: {', '.join(secured)}")
        else:
            print(f"{SKIP} RLS already enabled on all ORM tables")

    # ── report ──────────────────────────────────────────────────────────────
    print("\n\033[1mFINAL users SCHEMA\033[0m")
    print("─" * 66)
    for col in inspect(engine).get_columns("users"):
        null = "NULL" if col["nullable"] else "NOT NULL"
        print(f"  {col['name']:<20} {str(col['type']):<26} {null}")

    with engine.connect() as conn:
        print("\n\033[1mUSERS\033[0m")
        print("─" * 66)
        rows = conn.execute(
            text("select email, role, is_active, is_approved, hashed_password from users")
        ).all()
        for email, role, active, approved, pw in rows:
            state = "LOCKED (no password)" if pw == UNUSABLE_PASSWORD else "has password"
            print(f"  {email:<34} {role:<12} active={active} approved={approved}  {state}")

    print(f"\n{OK} Migration complete.\n")
    print("Next: create a real admin you can actually log in as —")
    print("      python3 init_admin.py\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"\n{BAD} {type(exc).__name__}: {exc}\n")
        sys.exit(1)
