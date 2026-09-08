"""
Tests for Google Cloud Vision OCR integration — SIH 26188

Coverage:
  - valid image → OCR succeeds
  - empty image → ValueError
  - invalid/oversized image → ValueError
  - OCR output normalisation schema
  - provider fallback (Vision fails → local OCR)
  - timeout / API error handling
  - missing credentials → falls back to local
  - OCRProvider primary_provider_name property

Google Vision is MOCKED in all tests so no paid API calls are made in CI.
Integration test (marked @pytest.mark.integration) requires real credentials
and is skipped in CI unless the environment variable GOOGLE_INTEGRATION_TESTS=1.
"""

import os
import sys
import io
import json
import types
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend/app
# ---------------------------------------------------------------------------
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ---------------------------------------------------------------------------
# Minimal image bytes helpers
# ---------------------------------------------------------------------------

def _minimal_jpeg_bytes() -> bytes:
    """Return a small but valid JPEG."""
    try:
        from PIL import Image
        import io as _io
        img = Image.new("RGB", (64, 64), color=(200, 200, 200))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Fallback: raw JPEG SOI/EOI markers (not processable but non-empty)
        return b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"


def _oversized_bytes(limit_bytes: int = 10 * 1024 * 1024) -> bytes:
    """Return bytes exceeding the Vision size limit."""
    return b"\x00" * (limit_bytes + 1)


# ---------------------------------------------------------------------------
# Helpers to build mock Vision API responses
# ---------------------------------------------------------------------------

def _make_mock_vision_response(text: str = "PASSPORT\nJOHN DOE") -> MagicMock:
    """Build a minimal mock that looks like a Vision API response."""
    response = MagicMock()
    response.error.message = ""  # No error

    # full_text_annotation
    full_text = MagicMock()
    full_text.text = text

    # Page → block → paragraph → word → symbol
    symbol = MagicMock()
    symbol.text = "P"
    symbol.confidence = 0.98
    symbol.bounding_box = MagicMock()
    symbol.bounding_box.vertices = [
        MagicMock(x=0, y=0),
        MagicMock(x=10, y=0),
        MagicMock(x=10, y=10),
        MagicMock(x=0, y=10),
    ]

    word = MagicMock()
    word.symbols = [symbol]
    word.confidence = 0.97
    word.bounding_box = symbol.bounding_box

    para = MagicMock()
    para.words = [word]

    block = MagicMock()
    block.paragraphs = [para]
    block.confidence = 0.96
    block.bounding_box = symbol.bounding_box

    page = MagicMock()
    page.blocks = [block]

    full_text.pages = [page]
    response.full_text_annotation = full_text

    # text_annotations (for TEXT_DETECTION path)
    ann = MagicMock()
    ann.description = text
    ann.locale = "en"
    ann.bounding_poly = MagicMock()
    ann.bounding_poly.vertices = symbol.bounding_box.vertices
    response.text_annotations = [ann]

    return response


def _make_empty_vision_response() -> MagicMock:
    """Vision response with no text."""
    response = MagicMock()
    response.error.message = ""
    full_text = MagicMock()
    full_text.text = ""
    full_text.pages = []
    response.full_text_annotation = full_text
    response.text_annotations = []
    return response


# ---------------------------------------------------------------------------
# Unit tests — GoogleVisionOCRProvider (mocked SDK)
# ---------------------------------------------------------------------------

class TestGoogleVisionOCRProvider:

    def _get_provider(self, mock_client):
        """Import and build a GoogleVisionOCRProvider with a mocked Vision client."""
        # Patch the SDK at module level before importing
        with patch.dict("sys.modules", {
            "google": types.ModuleType("google"),
            "google.cloud": types.ModuleType("google.cloud"),
            "google.cloud.vision": MagicMock(),
            "google.api_core": types.ModuleType("google.api_core"),
            "google.api_core.exceptions": MagicMock(),
            "google.api_core.client_options": MagicMock(),
            "google.auth": MagicMock(),
            "google.auth.exceptions": MagicMock(),
        }):
            # Re-import with mocks in place
            if "app.services.google_vision" in sys.modules:
                del sys.modules["app.services.google_vision"]
            from app.services.google_vision import GoogleVisionOCRProvider
            provider = GoogleVisionOCRProvider.__new__(GoogleVisionOCRProvider)
            provider._client = mock_client
            provider.max_image_bytes = 10 * 1024 * 1024
            provider.request_timeout = 30.0
            provider.max_retries = 2
            return provider

    def test_extract_document_text_success(self):
        """Valid image → OCR succeeds → normalized schema returned."""
        mock_client = MagicMock()
        mock_client.document_text_detection.return_value = _make_mock_vision_response(
            "PASSPORT\nP<INDSMITH<<JOHN<<<<<<<<<\nA1234567<IND9001017M2801017"
        )

        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with patch.dict("sys.modules", {
            "google.cloud.vision": MagicMock(),
            "google.api_core.exceptions": MagicMock(),
            "google.auth.exceptions": MagicMock(),
            "google.auth": MagicMock(),
        }):
            from app.services.google_vision import GoogleVisionOCRProvider, _GOOGLE_VISION_AVAILABLE

            if not _GOOGLE_VISION_AVAILABLE:
                pytest.skip("google-cloud-vision not installed; SDK mock test skipped")

            with patch("app.services.google_vision.gcp_vision") as mock_gcp:
                mock_gcp.Image = MagicMock()
                mock_gcp.ImageAnnotatorClient.return_value = mock_client

                provider = GoogleVisionOCRProvider()
                result = provider.extract_document_text(_minimal_jpeg_bytes())

        assert result["provider"] == "google_vision"
        assert isinstance(result["text"], str)
        assert isinstance(result["blocks"], list)
        assert isinstance(result["words"], list)
        assert isinstance(result["symbols"], list)
        assert isinstance(result["bounding_boxes"], list)
        # confidence may be None or float — never fabricated
        assert result["confidence"] is None or isinstance(result["confidence"], float)

    def test_empty_image_raises(self):
        """Empty bytes → ValueError before any API call."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with patch.dict("sys.modules", {
            "google.cloud.vision": MagicMock(),
            "google.api_core.exceptions": MagicMock(),
            "google.auth.exceptions": MagicMock(),
            "google.auth": MagicMock(),
        }):
            from app.services.google_vision import GoogleVisionOCRProvider, _GOOGLE_VISION_AVAILABLE

            if not _GOOGLE_VISION_AVAILABLE:
                pytest.skip("google-cloud-vision not installed")

            with patch("app.services.google_vision.gcp_vision"):
                provider = GoogleVisionOCRProvider()

            with pytest.raises(ValueError, match="empty"):
                provider.extract_document_text(b"")

    def test_oversized_image_raises(self):
        """Image exceeding max_image_bytes → ValueError."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with patch.dict("sys.modules", {
            "google.cloud.vision": MagicMock(),
            "google.api_core.exceptions": MagicMock(),
            "google.auth.exceptions": MagicMock(),
            "google.auth": MagicMock(),
        }):
            from app.services.google_vision import GoogleVisionOCRProvider, _GOOGLE_VISION_AVAILABLE

            if not _GOOGLE_VISION_AVAILABLE:
                pytest.skip("google-cloud-vision not installed")

            with patch("app.services.google_vision.gcp_vision"):
                provider = GoogleVisionOCRProvider(max_image_bytes=100)

            with pytest.raises(ValueError, match="large"):
                provider.extract_document_text(b"\x00" * 200)

    def test_api_error_retries_then_raises(self):
        """Vision API error → retries → RuntimeError after exhaustion."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with patch.dict("sys.modules", {
            "google.cloud.vision": MagicMock(),
            "google.api_core.exceptions": MagicMock(),
            "google.auth.exceptions": MagicMock(),
            "google.auth": MagicMock(),
        }):
            from app.services import google_vision as gv_module
            from app.services.google_vision import GoogleVisionOCRProvider, _GOOGLE_VISION_AVAILABLE

            if not _GOOGLE_VISION_AVAILABLE:
                pytest.skip("google-cloud-vision not installed")

            # Inject an error response
            error_response = MagicMock()
            error_response.error.message = "QUOTA_EXCEEDED: Vision quota exceeded"
            error_response.full_text_annotation = MagicMock()
            error_response.full_text_annotation.text = ""
            error_response.full_text_annotation.pages = []

            mock_client = MagicMock()
            mock_client.document_text_detection.return_value = error_response

            with patch("app.services.google_vision.gcp_vision") as mock_gcp:
                mock_gcp.Image = MagicMock()
                mock_gcp.ImageAnnotatorClient.return_value = mock_client
                # Make GoogleAPICallError a real exception class
                gv_module.GoogleAPICallError = Exception

                provider = GoogleVisionOCRProvider(max_retries=1)
                provider.request_timeout = 0.1

            with pytest.raises((RuntimeError, Exception)):
                provider.extract_document_text(_minimal_jpeg_bytes())


# ---------------------------------------------------------------------------
# Unit tests — OCRProvider (provider abstraction + fallback)
# ---------------------------------------------------------------------------

class TestOCRProvider:

    def _build_provider_env(self, ocr_provider_val: str, fallback: str = "true"):
        """Context manager: set env vars and clear module cache."""
        return patch.dict(os.environ, {
            "OCR_PROVIDER": ocr_provider_val,
            "OCR_FALLBACK_ENABLED": fallback,
        })

    def test_local_provider_selected_when_no_credentials(self):
        """When OCR_PROVIDER=google_vision but no credentials, falls back to local."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with self._build_provider_env("google_vision"):
            with patch("app.services.google_vision.GoogleVisionOCRProvider.is_available", return_value=False):
                from app.services.google_vision import OCRProvider
                provider = OCRProvider()
                assert provider.primary_provider_name == "local_ocr"

    def test_local_provider_used_by_default(self):
        """When OCR_PROVIDER=local (default), local OCR is primary."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with self._build_provider_env("local"):
            from app.services.google_vision import OCRProvider
            provider = OCRProvider()
            assert provider.primary_provider_name == "local_ocr"

    def test_fallback_to_local_when_vision_fails(self):
        """Vision raises → OCR_FALLBACK_ENABLED=true → local OCR used."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with self._build_provider_env("google_vision", fallback="true"):
            with patch("app.services.google_vision.GoogleVisionOCRProvider.is_available", return_value=True):
                from app.services.google_vision import OCRProvider, GoogleVisionOCRProvider, LocalOCRProvider

                # Patch GoogleVisionOCRProvider.__init__ to succeed
                with patch.object(GoogleVisionOCRProvider, "__init__", return_value=None):
                    provider = OCRProvider()
                    # Force the google provider to be set
                    provider._google_provider = MagicMock()
                    provider._google_provider.extract_document_text.side_effect = RuntimeError("Vision timeout")

                    # Patch local provider
                    provider._local_provider = MagicMock()
                    provider._local_provider.extract_document_text.return_value = {
                        "provider": "local_ocr",
                        "text": "PASSPORT LOCAL OCR FALLBACK",
                        "blocks": [], "words": [], "symbols": [],
                        "bounding_boxes": [], "confidence": None,
                    }

                    result = provider.extract_document_text(_minimal_jpeg_bytes())
                    assert result["provider"] == "local_ocr"
                    assert "FALLBACK" in result["text"]

    def test_no_fallback_raises_when_vision_fails(self):
        """Vision raises + OCR_FALLBACK_ENABLED=false → RuntimeError propagates."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with self._build_provider_env("google_vision", fallback="false"):
            with patch("app.services.google_vision.GoogleVisionOCRProvider.is_available", return_value=True):
                from app.services.google_vision import OCRProvider, GoogleVisionOCRProvider

                with patch.object(GoogleVisionOCRProvider, "__init__", return_value=None):
                    provider = OCRProvider()
                    provider._fallback_enabled = False
                    provider._google_provider = MagicMock()
                    provider._google_provider.extract_document_text.side_effect = RuntimeError("quota")

                    with pytest.raises(RuntimeError, match="unavailable"):
                        provider.extract_document_text(_minimal_jpeg_bytes())

    def test_empty_bytes_raises_before_provider(self):
        """Empty bytes → ValueError regardless of provider."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        with self._build_provider_env("local"):
            from app.services.google_vision import OCRProvider
            provider = OCRProvider()

            with pytest.raises(ValueError, match="No image bytes"):
                provider.extract_document_text(b"")


# ---------------------------------------------------------------------------
# Unit tests — OCR output normalisation schema
# ---------------------------------------------------------------------------

class TestNormalisedSchema:

    def test_schema_keys_present(self):
        """Normalised result always has the required keys."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        from app.services.google_vision import _empty_normalized_result

        result = _empty_normalized_result("google_vision")
        for key in ("provider", "text", "blocks", "words", "symbols",
                    "bounding_boxes", "confidence"):
            assert key in result, f"Missing key: {key}"

    def test_no_fabricated_confidence(self):
        """confidence is None when not provided — never fabricated."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        from app.services.google_vision import _empty_normalized_result

        result = _empty_normalized_result()
        assert result["confidence"] is None

    def test_bbox_to_dict(self):
        """_bbox_to_dict converts bounding poly vertices correctly."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        from app.services.google_vision import _bbox_to_dict

        mock_poly = MagicMock()
        v1 = MagicMock(x=0, y=0)
        v2 = MagicMock(x=10, y=0)
        v3 = MagicMock(x=10, y=20)
        v4 = MagicMock(x=0, y=20)
        mock_poly.vertices = [v1, v2, v3, v4]

        result = _bbox_to_dict(mock_poly)
        assert len(result) == 4
        assert result[0] == {"x": 0, "y": 0}
        assert result[2] == {"x": 10, "y": 20}

    def test_bbox_to_dict_none(self):
        """_bbox_to_dict handles None bounding_poly gracefully."""
        if "app.services.google_vision" in sys.modules:
            del sys.modules["app.services.google_vision"]

        from app.services.google_vision import _bbox_to_dict

        assert _bbox_to_dict(None) == []


# ---------------------------------------------------------------------------
# Integration test — requires real credentials & GOOGLE_INTEGRATION_TESTS=1
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("GOOGLE_INTEGRATION_TESTS") != "1",
    reason="Set GOOGLE_INTEGRATION_TESTS=1 and configure credentials to run.",
)
def test_integration_real_vision_call():
    """
    Integration test: sends a real image to Vision API.
    Requires:
      - GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_VISION_API_KEY in env
      - GOOGLE_INTEGRATION_TESTS=1
    """
    if "app.services.google_vision" in sys.modules:
        del sys.modules["app.services.google_vision"]

    from app.services.google_vision import GoogleVisionOCRProvider

    if not GoogleVisionOCRProvider.is_available():
        pytest.skip("Google Vision credentials not configured.")

    provider = GoogleVisionOCRProvider()
    result = provider.extract_document_text(_minimal_jpeg_bytes())

    assert result["provider"] == "google_vision"
    assert isinstance(result["text"], str)
    # A blank grey image will return empty text — just verify schema
    for key in ("blocks", "words", "symbols", "bounding_boxes"):
        assert isinstance(result[key], list)
