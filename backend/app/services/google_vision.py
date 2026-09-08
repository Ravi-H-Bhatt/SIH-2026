"""
Google Cloud Vision API Service — SIH 26188

Role in the pipeline:
  Camera/Upload → Supabase private storage → FastAPI → Google Cloud Vision OCR
  → normalized text/coordinates → MRZ parser → document validation → forensics
  → face analysis → identity engine → risk engine

Google Vision is ONLY the OCR/text-extraction layer.
It does NOT replace:
  - MRZ check-digit validation
  - Document forensics / tamper detection
  - Face verification / identity matching
  - Risk engine

Authentication:
  Preferred: Application Default Credentials / service account JSON
  (GOOGLE_APPLICATION_CREDENTIALS=/abs/path/key.json)
  Optional fallback: GOOGLE_VISION_API_KEY for testing only.

Per SIH26188_MASTER_AGENT_PROMPT.md — never expose credentials to the browser.
Never send continuous camera frames; only OCR the captured/uploaded image.
"""

import logging
import time
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import — fails gracefully so the backend starts without the SDK
# installed (unit tests use mocks, CI uses local OCR fallback).
# ---------------------------------------------------------------------------
try:
    from google.cloud import vision as gcp_vision
    from google.api_core.exceptions import GoogleAPICallError, RetryError
    from google.auth.exceptions import DefaultCredentialsError, TransportError

    _GOOGLE_VISION_AVAILABLE = True
except ImportError:
    _GOOGLE_VISION_AVAILABLE = False
    gcp_vision = None  # type: ignore
    GoogleAPICallError = Exception  # type: ignore
    RetryError = Exception  # type: ignore
    DefaultCredentialsError = Exception  # type: ignore
    TransportError = Exception  # type: ignore


# ---------------------------------------------------------------------------
# Normalised OCR result schema
# ---------------------------------------------------------------------------

def _empty_normalized_result(provider: str = "google_vision") -> Dict[str, Any]:
    """Return an empty but schema-valid normalized OCR result."""
    return {
        "provider": provider,
        "text": "",
        "blocks": [],
        "words": [],
        "symbols": [],
        "bounding_boxes": [],
        "confidence": None,
    }


def _bbox_to_dict(bounding_poly) -> List[Dict[str, int]]:
    """Convert a Vision API BoundingPoly to a serialisable list of {x, y} vertices."""
    if bounding_poly is None:
        return []
    return [{"x": v.x, "y": v.y} for v in bounding_poly.vertices]


# ---------------------------------------------------------------------------
# Google Cloud Vision provider
# ---------------------------------------------------------------------------

class GoogleVisionOCRProvider:
    """
    Calls the Google Cloud Vision API for document OCR.

    Instantiation will fail with a clear error if:
      - the google-cloud-vision SDK is not installed, OR
      - credentials cannot be resolved from the environment.

    Use GoogleVisionOCRProvider.is_available() to check before instantiating.
    """

    def __init__(
        self,
        max_image_bytes: int = 10 * 1024 * 1024,   # 10 MB
        request_timeout: float = 30.0,
        max_retries: int = 2,
        api_key: Optional[str] = None,
    ) -> None:
        if not _GOOGLE_VISION_AVAILABLE:
            raise RuntimeError(
                "google-cloud-vision is not installed. "
                "Run: pip install google-cloud-vision==3.7.2"
            )

        self.max_image_bytes = max_image_bytes
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        # Build client — ADC / GOOGLE_APPLICATION_CREDENTIALS is resolved
        # automatically by the Google Auth library.
        # api_key is only used as a last-resort override for quick testing.
        if api_key:
            # API-key mode: build a custom client options object.
            # Note: service-account / ADC is strongly preferred for production.
            from google.api_core.client_options import ClientOptions
            self._client = gcp_vision.ImageAnnotatorClient(
                client_options=ClientOptions(api_key=api_key)
            )
            logger.info("[GoogleVision] Initialized with API key (non-ADC mode).")
        else:
            self._client = gcp_vision.ImageAnnotatorClient()
            logger.info("[GoogleVision] Initialized with Application Default Credentials.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Calls Vision TEXT_DETECTION (faster, good for typed text / MRZ zones).

        Returns normalised OCR result dict.
        Does NOT fabricate confidence when the API doesn't provide one.
        """
        return self._call_vision(image_bytes, use_document_text=False)

    def extract_document_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Calls Vision DOCUMENT_TEXT_DETECTION (better layout analysis,
        recommended for full-page passport/ID documents).

        Returns normalised OCR result dict.
        """
        return self._call_vision(image_bytes, use_document_text=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_vision(
        self,
        image_bytes: bytes,
        use_document_text: bool = True,
    ) -> Dict[str, Any]:
        """Execute Vision API call with retry logic; return normalized result."""

        # --- Size guard ---
        if not image_bytes:
            logger.warning("[GoogleVision] Received empty image bytes.")
            raise ValueError("Image bytes are empty.")

        if len(image_bytes) > self.max_image_bytes:
            size_mb = len(image_bytes) / (1024 * 1024)
            raise ValueError(
                f"Image too large: {size_mb:.1f} MB "
                f"(limit {self.max_image_bytes // (1024*1024)} MB). "
                "Resize or compress the image before sending."
            )

        image = gcp_vision.Image(content=image_bytes)
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 2):  # attempts = max_retries + 1
            try:
                if use_document_text:
                    response = self._client.document_text_detection(
                        image=image,
                        timeout=self.request_timeout,
                    )
                else:
                    response = self._client.text_detection(
                        image=image,
                        timeout=self.request_timeout,
                    )

                # Surface API-level errors (quota, auth, etc.)
                if response.error.message:
                    raise GoogleAPICallError(
                        f"Vision API error: {response.error.message}"
                    )

                return self._normalize_response(response, use_document_text)

            except (GoogleAPICallError, RetryError, TransportError) as exc:
                last_error = exc
                logger.warning(
                    "[GoogleVision] Attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )
                if attempt <= self.max_retries:
                    time.sleep(0.5 * attempt)  # simple back-off

        # All retries exhausted
        raise RuntimeError(
            f"Google Vision failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error}"
        ) from last_error

    def _normalize_response(
        self,
        response,
        use_document_text: bool,
    ) -> Dict[str, Any]:
        """
        Convert Vision API response to a stable, serialisable dict.

        Schema:
          provider        : "google_vision"
          text            : str  — full extracted text
          blocks          : list — page-level block annotations
          words           : list — word-level annotations with bboxes
          symbols         : list — symbol/character annotations (document mode)
          bounding_boxes  : list — top-level text annotations with bboxes
          confidence      : float | None — overall confidence if provided

        We never fabricate a confidence score where the API does not supply one.
        """
        result = _empty_normalized_result("google_vision")

        if use_document_text:
            # DOCUMENT_TEXT_DETECTION → full_text_annotation
            full_text = response.full_text_annotation
            if not full_text:
                return result

            result["text"] = full_text.text

            # Build block / word / symbol lists from pages
            for page in full_text.pages:
                for block in page.blocks:
                    block_text_parts = []
                    block_words = []

                    for para in block.paragraphs:
                        for word in para.words:
                            word_text = "".join(s.text for s in word.symbols)
                            word_entry = {
                                "text": word_text,
                                "confidence": word.confidence if word.confidence > 0 else None,
                                "bounding_box": _bbox_to_dict(word.bounding_box),
                            }
                            result["words"].append(word_entry)
                            block_words.append(word_text)

                            for symbol in word.symbols:
                                result["symbols"].append({
                                    "text": symbol.text,
                                    "confidence": symbol.confidence if symbol.confidence > 0 else None,
                                    "bounding_box": _bbox_to_dict(symbol.bounding_box),
                                })

                        block_text_parts.append(
                            " ".join(
                                "".join(s.text for s in w.symbols)
                                for w in para.words
                            )
                        )

                    result["blocks"].append({
                        "text": "\n".join(block_text_parts),
                        "words": block_words,
                        "confidence": block.confidence if block.confidence > 0 else None,
                        "bounding_box": _bbox_to_dict(block.bounding_box),
                    })

            # Overall confidence: use mean of word confidences when available.
            word_confs = [
                w["confidence"]
                for w in result["words"]
                if w["confidence"] is not None
            ]
            result["confidence"] = (
                round(sum(word_confs) / len(word_confs), 4)
                if word_confs
                else None
            )

        else:
            # TEXT_DETECTION → text_annotations list
            annotations = response.text_annotations
            if not annotations:
                return result

            # First annotation = full text block
            result["text"] = annotations[0].description

            result["bounding_boxes"] = [
                {
                    "text": ann.description,
                    "locale": ann.locale or None,
                    "bounding_box": _bbox_to_dict(ann.bounding_poly),
                }
                for ann in annotations
            ]
            # No reliable per-word confidence in TEXT_DETECTION mode
            result["confidence"] = None

        return result

    # ------------------------------------------------------------------
    # Class-level helper
    # ------------------------------------------------------------------

    @classmethod
    def is_available(cls) -> bool:
        """
        True if the SDK is installed AND some credential is usable.

        Two independent auth modes are supported and either is sufficient:

          1. An API key (GOOGLE_VISION_API_KEY).
          2. Application Default Credentials / a service-account JSON.

        This previously only probed google.auth.default(), so an API-key-only
        setup was reported unavailable and the provider silently fell back to
        local OCR — which then failed too if Tesseract was not installed.
        """
        if not _GOOGLE_VISION_AVAILABLE:
            return False

        from app.core.config import settings

        # API key mode needs no ADC lookup at all.
        if settings.GOOGLE_VISION_API_KEY:
            return True

        try:
            import google.auth

            google.auth.default()  # raises DefaultCredentialsError if unset
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Google Cloud Vision provider — REST / API-key mode (no SDK required)
# ---------------------------------------------------------------------------

class GoogleVisionRESTProvider:
    """
    Calls the Vision REST endpoint directly with an API key.

    Why this exists alongside GoogleVisionOCRProvider:
      * The google-cloud-vision SDK pulls in grpc, protobuf and google-api-core
        — tens of megabytes, which matters for a serverless deployment budget.
      * The SDK also prefers Application Default Credentials. Getting it to work
        in pure API-key mode is awkward, and if the SDK is missing entirely
        (as it was here) OCR silently degraded to a local engine that then
        failed because Tesseract was not installed either.

    `images:annotate` over HTTPS with `?key=` needs nothing but the standard
    library, so this path has no import that can fail at runtime.
    """

    ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"

    def __init__(
        self,
        api_key: str,
        max_image_bytes: int = 10 * 1024 * 1024,
        request_timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        if not api_key:
            raise RuntimeError("GoogleVisionRESTProvider requires an API key.")
        self._api_key = api_key
        self.max_image_bytes = max_image_bytes
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        logger.info("[GoogleVision] REST provider initialized (API-key mode).")

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        return self._call(image_bytes, "TEXT_DETECTION")

    def extract_document_text(self, image_bytes: bytes) -> Dict[str, Any]:
        return self._call(image_bytes, "DOCUMENT_TEXT_DETECTION")

    # ------------------------------------------------------------------

    def _call(self, image_bytes: bytes, feature: str) -> Dict[str, Any]:
        import base64
        import json as _json
        import ssl
        import urllib.error
        import urllib.request

        if not image_bytes:
            raise ValueError("Image bytes are empty.")
        if len(image_bytes) > self.max_image_bytes:
            raise ValueError(
                f"Image too large: {len(image_bytes) / 1048576:.1f} MB "
                f"(limit {self.max_image_bytes // 1048576} MB)."
            )

        try:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # pragma: no cover
            ctx = ssl.create_default_context()

        payload = _json.dumps(
            {
                "requests": [
                    {
                        "image": {"content": base64.b64encode(image_bytes).decode()},
                        "features": [{"type": feature}],
                        # MRZ is not natural language; language hints would only
                        # bias the recogniser toward dictionary words.
                        "imageContext": {"languageHints": ["en"]},
                    }
                ]
            }
        ).encode()

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 2):
            try:
                req = urllib.request.Request(
                    f"{self.ENDPOINT}?key={self._api_key}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    req, timeout=self.request_timeout, context=ctx
                ) as resp:
                    body = _json.loads(resp.read().decode("utf-8"))
                return self._normalize(body, feature)

            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                last_error = RuntimeError(f"Vision HTTP {exc.code}: {detail}")
                # 4xx other than 429 will not succeed on retry.
                if exc.code < 500 and exc.code != 429:
                    raise last_error from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc

            if attempt <= self.max_retries:
                time.sleep(0.5 * attempt)

        raise RuntimeError(
            f"Google Vision REST failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error}"
        ) from last_error

    @staticmethod
    def _normalize(body: Dict[str, Any], feature: str) -> Dict[str, Any]:
        """Map the REST JSON onto the same schema the SDK path produces."""
        result = _empty_normalized_result("google_vision")

        if body.get("error"):
            raise RuntimeError(f"Vision API error: {body['error'].get('message')}")

        responses = body.get("responses") or [{}]
        resp = responses[0] or {}
        if resp.get("error"):
            raise RuntimeError(f"Vision API error: {resp['error'].get('message')}")

        def verts(poly):
            return [
                {"x": v.get("x", 0), "y": v.get("y", 0)}
                for v in (poly or {}).get("vertices", [])
            ]

        if feature == "DOCUMENT_TEXT_DETECTION":
            full = resp.get("fullTextAnnotation") or {}
            result["text"] = full.get("text", "") or ""

            for page in full.get("pages", []):
                for block in page.get("blocks", []):
                    block_lines, block_words = [], []
                    for para in block.get("paragraphs", []):
                        for word in para.get("words", []):
                            text = "".join(
                                s.get("text", "") for s in word.get("symbols", [])
                            )
                            conf = word.get("confidence")
                            result["words"].append({
                                "text": text,
                                "confidence": conf if conf else None,
                                "bounding_box": verts(word.get("boundingBox")),
                            })
                            block_words.append(text)
                            for sym in word.get("symbols", []):
                                sconf = sym.get("confidence")
                                result["symbols"].append({
                                    "text": sym.get("text", ""),
                                    "confidence": sconf if sconf else None,
                                    "bounding_box": verts(sym.get("boundingBox")),
                                })
                        block_lines.append(" ".join(
                            "".join(s.get("text", "") for s in w.get("symbols", []))
                            for w in para.get("words", [])
                        ))
                    bconf = block.get("confidence")
                    result["blocks"].append({
                        "text": "\n".join(block_lines),
                        "words": block_words,
                        "confidence": bconf if bconf else None,
                        "bounding_box": verts(block.get("boundingBox")),
                    })

            confs = [w["confidence"] for w in result["words"] if w["confidence"]]
            result["confidence"] = round(sum(confs) / len(confs), 4) if confs else None
        else:
            annotations = resp.get("textAnnotations") or []
            if annotations:
                result["text"] = annotations[0].get("description", "")
                result["bounding_boxes"] = [
                    {
                        "text": a.get("description", ""),
                        "locale": a.get("locale") or None,
                        "bounding_box": verts(a.get("boundingPoly")),
                    }
                    for a in annotations
                ]

        return result


# ---------------------------------------------------------------------------
# Local OCR provider (existing backend OCR as fallback)
# ---------------------------------------------------------------------------

class LocalOCRProvider:
    """
    Thin wrapper around the existing OCRService so the provider abstraction
    has a consistent interface.  This is always the fallback when Google Vision
    is unavailable or returns an error.
    """

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Runs local OCR (existing OCRService / PaddleOCR) on in-memory bytes.
        Returns the same normalised schema as GoogleVisionOCRProvider.
        """
        import tempfile, os
        # Write bytes to a temp file so the existing service can process it.
        suffix = ".jpg"
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            # Lazy import to avoid circular imports at module load time.
            from app.services.ocr.ocr_service import ocr_service

            raw = ocr_service.process_document(tmp_path)
            text = raw.get("raw_ocr_text", "") or ""

            return {
                "provider": "local_ocr",
                "text": text,
                "blocks": [],
                "words": [],
                "symbols": [],
                "bounding_boxes": [],
                "confidence": None,
                "local_fields": raw,  # pass through structured fields for pipeline use
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def extract_document_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """Alias — local OCR has a single path."""
        return self.extract_text(image_bytes)


# ---------------------------------------------------------------------------
# OCR provider abstraction
# ---------------------------------------------------------------------------

class OCRProvider:
    """
    Unified OCR provider abstraction.

    Selection order (configured via env vars):
      1. GoogleVisionOCRProvider   (when OCR_PROVIDER=google_vision AND credentials valid)
      2. LocalOCRProvider          (always available as fallback)

    Environment variables:
      OCR_PROVIDER=google_vision        — selects Google Vision as primary
      OCR_FALLBACK_ENABLED=true         — enables local fallback on any Vision error
      GOOGLE_VISION_API_KEY=...         — optional API key (ADC is preferred)
      VISION_MAX_IMAGE_BYTES=...        — max bytes before rejecting image (default 10 MB)
      VISION_REQUEST_TIMEOUT_SECONDS=.. — per-request timeout (default 30 s)
      VISION_MAX_RETRIES=...            — retry count on transient errors (default 2)
    """

    def __init__(self) -> None:
        # Read from the Settings object, NOT os.getenv.
        #
        # pydantic-settings parses backend/.env into `settings`; it does not
        # export those values into os.environ. So every os.getenv() call here
        # returned None, OCR_PROVIDER silently defaulted to "local", and
        # Google Vision was never constructed even though it was configured.
        from app.core.config import settings

        self._ocr_provider_name: str = (settings.OCR_PROVIDER or "local").lower()
        self._fallback_enabled: bool = settings.OCR_FALLBACK_ENABLED

        max_bytes = settings.VISION_MAX_IMAGE_BYTES
        timeout = settings.VISION_REQUEST_TIMEOUT_SECONDS
        max_retries = settings.VISION_MAX_RETRIES
        api_key = settings.GOOGLE_VISION_API_KEY or None

        self._google_provider = None
        self._local_provider = LocalOCRProvider()

        if self._ocr_provider_name == "google_vision":
            # Preference order:
            #   1. REST + API key  — stdlib only, no SDK, no ADC.
            #   2. SDK + ADC       — service-account / gcloud login.
            # An API key is checked first because it is the configuration that
            # actually exists here, and because it keeps the deployment slim.
            if api_key:
                try:
                    self._google_provider = GoogleVisionRESTProvider(
                        api_key=api_key,
                        max_image_bytes=max_bytes,
                        request_timeout=timeout,
                        max_retries=max_retries,
                    )
                    logger.info("[OCRProvider] Google Vision (REST) is the primary OCR provider.")
                except Exception as exc:
                    logger.warning("[OCRProvider] Vision REST init failed: %s", exc)

            if self._google_provider is None and GoogleVisionOCRProvider.is_available():
                try:
                    self._google_provider = GoogleVisionOCRProvider(
                        max_image_bytes=max_bytes,
                        request_timeout=timeout,
                        max_retries=max_retries,
                        api_key=api_key,
                    )
                    logger.info("[OCRProvider] Google Vision (SDK) is the primary OCR provider.")
                except Exception as exc:
                    logger.warning("[OCRProvider] Vision SDK init failed: %s", exc)

            if self._google_provider is None:
                logger.warning(
                    "[OCRProvider] OCR_PROVIDER=google_vision but no usable credentials. "
                    "Set GOOGLE_VISION_API_KEY, or GOOGLE_APPLICATION_CREDENTIALS with "
                    "the SDK installed. Falling back to local OCR."
                )

    # ------------------------------------------------------------------

    def extract_document_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Run OCR with automatic fallback.

          Primary  : Google Vision DOCUMENT_TEXT_DETECTION (if configured + available)
          Fallback : Local OCR (PaddleOCR / existing OCR service)

        Never returns a fabricated result. Never silently fails.
        Raises only when both providers fail AND fallback is disabled.
        """
        if not image_bytes:
            raise ValueError("No image bytes provided to OCR provider.")

        if self._google_provider is not None:
            try:
                result = self._google_provider.extract_document_text(image_bytes)
                if result["text"]:
                    logger.info(
                        "[OCRProvider] Google Vision OCR succeeded (%d chars).",
                        len(result["text"]),
                    )
                    return result
                logger.warning(
                    "[OCRProvider] Google Vision returned empty OCR text."
                )
            except Exception as exc:
                logger.error(
                    "[OCRProvider] Google Vision OCR failed: %s", exc
                )
                if not self._fallback_enabled:
                    raise RuntimeError(
                        f"Google Vision unavailable — retry. Error: {exc}"
                    ) from exc
                logger.info("[OCRProvider] Using local OCR fallback.")

        # Fallback path
        try:
            result = self._local_provider.extract_document_text(image_bytes)
            logger.info(
                "[OCRProvider] Local OCR fallback succeeded (%d chars).",
                len(result.get("text", "")),
            )
            return result
        except Exception as exc:
            raise RuntimeError(
                f"Both Google Vision and local OCR failed. Last error: {exc}"
            ) from exc

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Convenience wrapper — uses DOCUMENT_TEXT_DETECTION (better for IDs/passports).
        """
        return self.extract_document_text(image_bytes)

    @property
    def primary_provider_name(self) -> str:
        """Return which provider is currently active as primary."""
        if self._google_provider is not None:
            return "google_vision"
        return "local_ocr"

    @property
    def fallback_enabled(self) -> bool:
        return self._fallback_enabled


# ---------------------------------------------------------------------------
# Module-level singleton — import this in the pipeline
# ---------------------------------------------------------------------------
ocr_provider = OCRProvider()
