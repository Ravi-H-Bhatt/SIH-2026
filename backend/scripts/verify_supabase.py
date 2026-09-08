#!/usr/bin/env python3
"""
Supabase preflight check.

Run this before starting the API. It answers, in order:
  1. Is a Supabase Postgres URL resolvable from the current .env?
  2. Does the connection actually open, and is it really Postgres?
  3. Do the ORM tables exist, and how many scans are stored?
  4. Is Supabase Storage reachable and are both buckets present + private?
  5. Which OCR provider will be used?
  6. Is blockchain anchoring on, and can it write?

Usage:
    cd backend && python3 scripts/verify_supabase.py
"""

from __future__ import annotations

import os
import sys

# Allow running as `python3 scripts/verify_supabase.py` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "\033[92m✓\033[0m"
BAD = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

failures: list[str] = []
warnings: list[str] = []


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")
    print("─" * 66)


def redact(url: str) -> str:
    """Strip credentials so the URL is safe to print."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


def main() -> int:
    print("\n\033[1mSUPABASE PREFLIGHT\033[0m")

    from app.core.config import settings

    # ── 1. URL resolution ───────────────────────────────────────────────────
    section("1. Postgres connection string")
    db_url = settings.resolved_database_url()

    if not db_url:
        print(f"{BAD} No database URL could be resolved.")
        failures.append(
            "Set SUPABASE_DB_PASSWORD in backend/.env\n"
            "     Supabase Dashboard -> Project Settings -> Database -> Database password"
        )
    elif not db_url.startswith("postgresql"):
        print(f"{BAD} Resolved to a non-Postgres URL: {redact(db_url)}")
        failures.append(
            "DATABASE_URL points at SQLite. Clear it and set SUPABASE_DB_PASSWORD instead."
        )
    else:
        print(f"{OK} {redact(db_url)}")
        ref = settings.supabase_project_ref
        print(f"  project ref : {ref}")
        print(f"  pooled      : {'yes (serverless-safe)' if ':6543' in db_url else 'no (direct, port 5432)'}")

    print(f"  REQUIRE_SUPABASE = {settings.REQUIRE_SUPABASE}")
    if not settings.REQUIRE_SUPABASE:
        print(f"{WARN} REQUIRE_SUPABASE is false — the app may silently fall back to SQLite.")
        warnings.append("Set REQUIRE_SUPABASE=true so misconfiguration fails loudly.")

    # ── 2 & 3. Live connection + schema ─────────────────────────────────────
    section("2. Live connection & schema")
    if not db_url or not db_url.startswith("postgresql"):
        print("  skipped — no valid Postgres URL")
    else:
        try:
            from sqlalchemy import create_engine, inspect, text

            engine = create_engine(db_url, connect_args={"connect_timeout": 10})
            with engine.connect() as conn:
                version = conn.execute(text("select version()")).scalar_one()
                print(f"{OK} Connected.")
                print(f"  {str(version).split('on')[0].strip()}")

                inspector = inspect(engine)
                tables = set(inspector.get_table_names())
                expected = {
                    "users", "scan_records", "extracted_data",
                    "forgery_results", "face_results", "risk_scores", "audit_logs",
                }
                missing = expected - tables
                if missing:
                    print(f"{WARN} Missing tables: {', '.join(sorted(missing))}")
                    warnings.append(
                        "Start the API once (`uvicorn main:app`) — it runs "
                        "create_all() and builds the schema automatically."
                    )
                else:
                    print(f"{OK} All 7 ORM tables present.")

                if "scan_records" in tables:
                    n = conn.execute(text("select count(*) from scan_records")).scalar_one()
                    print(f"  scan_records rows : {n}")
        except Exception as exc:
            print(f"{BAD} {type(exc).__name__}: {exc}")
            failures.append(
                "Could not connect. Check the DB password, and if your network "
                "blocks port 5432 switch to the pooler:\n"
                "     SUPABASE_DB_HOST=aws-0-<region>.pooler.supabase.com\n"
                "     SUPABASE_DB_PORT=6543\n"
                f"     SUPABASE_DB_USER=postgres.{settings.supabase_project_ref}"
            )

    # ── 4. Storage ──────────────────────────────────────────────────────────
    section("3. Supabase Storage")
    if not settings.supabase_storage_configured:
        print(f"{BAD} Not configured (needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).")
        failures.append("Document images would be written to local disk instead of Supabase.")
    else:
        try:
            from app.services.storage.supabase_storage import supabase_storage

            buckets = supabase_storage.list_buckets()
            by_name = {b.get("name"): b for b in buckets}
            print(f"{OK} Storage API reachable ({len(buckets)} bucket(s)).")

            for label, name in (
                ("documents", settings.STORAGE_DOCUMENT_BUCKET),
                ("faces", settings.STORAGE_FACE_BUCKET),
            ):
                bucket = by_name.get(name)
                if bucket is None:
                    print(f"{WARN} {label:<10} '{name}' missing — created on API startup.")
                    warnings.append(f"Bucket '{name}' does not exist yet.")
                elif bucket.get("public"):
                    print(f"{BAD} {label:<10} '{name}' is PUBLIC.")
                    failures.append(
                        f"Bucket '{name}' is public — passport images would be "
                        "world-readable. Set it to private in the dashboard."
                    )
                else:
                    print(f"{OK} {label:<10} '{name}' present and private.")
        except Exception as exc:
            print(f"{BAD} {type(exc).__name__}: {exc}")
            failures.append("Storage API unreachable — check SUPABASE_SERVICE_ROLE_KEY.")

    # ── 5. OCR ──────────────────────────────────────────────────────────────
    section("4. OCR provider")
    print(f"  OCR_PROVIDER = {settings.OCR_PROVIDER}")
    if settings.OCR_PROVIDER == "google_vision":
        if settings.google_vision_configured:
            how = "service account" if settings.GOOGLE_APPLICATION_CREDENTIALS else "API key"
            print(f"{OK} Google Cloud Vision configured via {how}.")
        else:
            print(f"{BAD} Google Vision selected but no credentials found.")
            failures.append("Set GOOGLE_VISION_API_KEY or GOOGLE_APPLICATION_CREDENTIALS.")
    else:
        import shutil

        binary = settings.TESSERACT_CMD or shutil.which("tesseract")
        if binary:
            print(f"{OK} Local OCR — tesseract at {binary}")
        else:
            print(f"{WARN} Local OCR selected but tesseract is not on PATH.")
            warnings.append("Run `brew install tesseract`, or set OCR_PROVIDER=google_vision.")

    # ── 6. Blockchain ───────────────────────────────────────────────────────
    section("5. Blockchain audit anchor")
    print("  SHA-256 canonical hash : always on (stored in Supabase)")
    if not settings.BLOCKCHAIN_ANCHOR_ENABLED:
        print(f"{OK} On-chain anchoring disabled — optional, nothing to do.")
    elif settings.blockchain_can_write:
        print(f"{OK} Write mode: anchors will be published on chain {settings.BLOCKCHAIN_CHAIN_ID}.")
    elif settings.blockchain_rpc_endpoint:
        print(f"{WARN} Read-only: RPC reachable but no funded signing key.")
        warnings.append(
            "Anchors can be verified but not created. See docs/BLOCKCHAIN_ANCHORING.md."
        )
    else:
        print(f"{WARN} Enabled but GOOGLE_BLOCKCHAIN_RPC_URL is unset/placeholder.")
        warnings.append("Set GOOGLE_BLOCKCHAIN_RPC_URL + GOOGLE_BLOCKCHAIN_API_KEY.")

    # ── Summary ─────────────────────────────────────────────────────────────
    section("SUMMARY")
    if failures:
        print(f"{BAD} {len(failures)} blocking issue(s):\n")
        for i, item in enumerate(failures, 1):
            print(f"  {i}. {item}")
    else:
        print(f"{OK} No blocking issues. Scans will persist to Supabase.")

    if warnings:
        print(f"\n{WARN} {len(warnings)} warning(s):\n")
        for i, item in enumerate(warnings, 1):
            print(f"  {i}. {item}")

    print()
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
