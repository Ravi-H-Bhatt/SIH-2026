"""
Supabase Storage adapter — every document scan and face capture is persisted
to a private Supabase Storage bucket. Local disk is used only as scratch space
while the OpenCV / OCR models read the image, then cleaned up.

Buckets (private, created via ensure_buckets() or the dashboard):
  - document-images
  - face-captures

Objects are addressed as `supabase://<bucket>/<object_path>` in the database so
a record is portable across environments. Browser-facing URLs are short-lived
signed URLs minted on read.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import ssl
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPABASE_SCHEME = "supabase://"

try:  # certifi keeps TLS verification working on stock macOS Python builds
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CONTEXT = ssl.create_default_context()


class StorageError(RuntimeError):
    """Raised when an object cannot be persisted to Supabase Storage."""


@dataclass
class StoredObject:
    """Result of persisting a single upload."""

    uri: str           # supabase://bucket/path  (or file:// when running detached)
    bucket: str
    object_path: str
    local_path: str    # temp path the ML pipeline reads from
    size_bytes: int
    backend: str       # "supabase" | "local"


class SupabaseStorageService:
    def __init__(self) -> None:
        self._base = (settings.SUPABASE_URL or "").rstrip("/")
        self._key = settings.SUPABASE_SERVICE_ROLE_KEY or ""

    # ── plumbing ────────────────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return bool(self._base and self._key)

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"Authorization": f"Bearer {self._key}", "apikey": self._key}
        if extra:
            headers.update(extra)
        return headers

    def _call(
        self,
        method: str,
        path: str,
        *,
        data: Optional[bytes] = None,
        headers: Optional[dict] = None,
        timeout: int = 45,
    ) -> bytes:
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, headers=self._headers(headers), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise StorageError(f"Supabase Storage {method} {path} -> {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise StorageError(f"Supabase Storage unreachable: {exc.reason}") from exc

    # ── setup ───────────────────────────────────────────────────────────────
    def ensure_buckets(self) -> None:
        """Idempotently creates the private buckets the app writes to."""
        if not self.enabled:
            return
        limit = settings.STORAGE_MAX_FILE_SIZE_MB * 1024 * 1024
        for bucket in (settings.STORAGE_DOCUMENT_BUCKET, settings.STORAGE_FACE_BUCKET):
            payload = json.dumps(
                {
                    "id": bucket,
                    "name": bucket,
                    "public": False,
                    "file_size_limit": limit,
                    "allowed_mime_types": [
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                        "application/pdf",
                    ],
                }
            ).encode()
            try:
                self._call(
                    "POST",
                    "/storage/v1/bucket",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                logger.info("Created Supabase Storage bucket '%s'.", bucket)
            except StorageError as exc:
                # 409 = already exists, which is the happy path on every restart.
                if "409" in str(exc) or "already exists" in str(exc).lower():
                    logger.debug("Bucket '%s' already present.", bucket)
                else:
                    logger.warning("Could not verify bucket '%s': %s", bucket, exc)

    def list_buckets(self) -> list[dict]:
        """
        Returns the project's buckets. Used by scripts/verify_supabase.py to
        confirm both buckets exist and are private before the first scan.
        """
        if not self.enabled:
            raise StorageError(
                "Supabase Storage is not configured "
                "(SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)."
            )
        raw = self._call("GET", "/storage/v1/bucket")
        parsed = json.loads(raw.decode("utf-8") or "[]")
        return parsed if isinstance(parsed, list) else []

    # ── writes ──────────────────────────────────────────────────────────────
    def store_upload(
        self,
        *,
        content: bytes,
        filename: str,
        bucket: str,
        scan_id: Optional[str] = None,
    ) -> StoredObject:
        """
        Writes bytes to a local temp file (for the ML pipeline) and uploads the
        same bytes to Supabase Storage.
        """
        max_bytes = settings.STORAGE_MAX_FILE_SIZE_MB * 1024 * 1024
        if not content:
            raise StorageError("Uploaded file is empty.")
        if len(content) > max_bytes:
            raise StorageError(
                f"File is {len(content) / 1_048_576:.1f} MB; limit is "
                f"{settings.STORAGE_MAX_FILE_SIZE_MB} MB."
            )

        safe_name = os.path.basename(filename or "upload.jpg").replace("\\", "_")
        ext = os.path.splitext(safe_name)[1].lower() or ".jpg"
        stamp = datetime.now(timezone.utc)
        object_path = (
            f"{stamp:%Y/%m/%d}/{scan_id or uuid.uuid4()}-{uuid.uuid4().hex[:8]}{ext}"
        )

        local_path = self._write_scratch(content, ext)

        if not self.enabled:
            logger.warning(
                "Supabase Storage is not configured (SUPABASE_URL / "
                "SUPABASE_SERVICE_ROLE_KEY missing) — keeping %s on local disk only.",
                safe_name,
            )
            return StoredObject(
                uri=f"file://{local_path}",
                bucket=bucket,
                object_path=object_path,
                local_path=local_path,
                size_bytes=len(content),
                backend="local",
            )

        content_type = mimetypes.guess_type(safe_name)[0] or "image/jpeg"
        self._call(
            "POST",
            f"/storage/v1/object/{bucket}/{object_path}",
            data=content,
            headers={
                "Content-Type": content_type,
                "x-upsert": "true",
                "cache-control": "3600",
            },
        )
        logger.info("Stored %s in Supabase bucket '%s'.", object_path, bucket)

        return StoredObject(
            uri=f"{SUPABASE_SCHEME}{bucket}/{object_path}",
            bucket=bucket,
            object_path=object_path,
            local_path=local_path,
            size_bytes=len(content),
            backend="supabase",
        )

    @staticmethod
    def _write_scratch(content: bytes, ext: str) -> str:
        scratch_dir = os.path.join(os.path.abspath(settings.UPLOAD_DIR), "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=ext, dir=scratch_dir)
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        return path

    # ── reads ───────────────────────────────────────────────────────────────
    @staticmethod
    def parse_uri(uri: str) -> Optional[Tuple[str, str]]:
        """`supabase://bucket/a/b.jpg` -> ("bucket", "a/b.jpg")."""
        if not uri or not uri.startswith(SUPABASE_SCHEME):
            return None
        remainder = uri[len(SUPABASE_SCHEME):]
        bucket, _, object_path = remainder.partition("/")
        if not bucket or not object_path:
            return None
        return bucket, object_path

    def signed_url(self, uri: Optional[str], ttl_seconds: Optional[int] = None) -> Optional[str]:
        """Mints a short-lived signed URL so the browser can render a private object."""
        parsed = self.parse_uri(uri or "")
        if not parsed or not self.enabled:
            return None
        bucket, object_path = parsed
        ttl = ttl_seconds or settings.STORAGE_SIGNED_URL_TTL_SECONDS
        try:
            raw = self._call(
                "POST",
                f"/storage/v1/object/sign/{bucket}/{object_path}",
                data=json.dumps({"expiresIn": ttl}).encode(),
                headers={"Content-Type": "application/json"},
                timeout=20,
            )
            signed = json.loads(raw).get("signedURL") or json.loads(raw).get("signedUrl")
            if not signed:
                return None
            return f"{self._base}/storage/v1{signed}" if signed.startswith("/") else signed
        except (StorageError, ValueError) as exc:
            logger.warning("Could not sign %s: %s", uri, exc)
            return None

    def download_to_temp(self, uri: Optional[str]) -> Optional[str]:
        """Pulls an object back down to disk (used when re-running the pipeline)."""
        parsed = self.parse_uri(uri or "")
        if not parsed or not self.enabled:
            return None
        bucket, object_path = parsed
        try:
            content = self._call("GET", f"/storage/v1/object/{bucket}/{object_path}", timeout=45)
        except StorageError as exc:
            logger.warning("Could not download %s: %s", uri, exc)
            return None
        return self._write_scratch(content, os.path.splitext(object_path)[1] or ".jpg")

    # ── cleanup ─────────────────────────────────────────────────────────────
    @staticmethod
    def cleanup_scratch(*paths: Optional[str]) -> None:
        if settings.KEEP_LOCAL_UPLOAD_COPY:
            return
        for path in paths:
            if not path:
                continue
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as exc:  # pragma: no cover
                logger.debug("Could not remove scratch file %s: %s", path, exc)


supabase_storage = SupabaseStorageService()
