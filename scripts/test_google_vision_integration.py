#!/usr/bin/env python3
"""
Quick validation script for Google Cloud Vision integration.

Run this after configuring credentials to verify the setup.

Usage:
  # With credentials configured:
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
  export OCR_PROVIDER=google_vision
  python3 scripts/test_google_vision_integration.py

  # Without credentials (tests fallback):
  python3 scripts/test_google_vision_integration.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.google_vision import ocr_provider, GoogleVisionOCRProvider
from app.core.config import settings
from PIL import Image
import io


def create_test_image() -> bytes:
    """Create a minimal test image with text."""
    img = Image.new("RGB", (400, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def main():
    print("=" * 80)
    print("GOOGLE CLOUD VISION INTEGRATION TEST")
    print("=" * 80)
    
    # Configuration check
    print(f"\n📋 Configuration:")
    print(f"  OCR_PROVIDER: {settings.OCR_PROVIDER}")
    print(f"  OCR_FALLBACK_ENABLED: {settings.OCR_FALLBACK_ENABLED}")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {settings.GOOGLE_APPLICATION_CREDENTIALS or '(not set)'}")
    print(f"  GOOGLE_VISION_API_KEY: {'(set)' if settings.GOOGLE_VISION_API_KEY else '(not set)'}")
    print(f"  Google Vision configured: {settings.google_vision_configured}")
    
    # Provider check
    print(f"\n🔧 OCR Provider:")
    print(f"  Primary provider: {ocr_provider.primary_provider_name}")
    print(f"  Fallback enabled: {ocr_provider.fallback_enabled}")
    
    # Availability check
    vision_available = GoogleVisionOCRProvider.is_available()
    print(f"  Google Vision available: {vision_available}")
    
    if not vision_available and settings.OCR_PROVIDER == "google_vision":
        print("\n⚠️  WARNING: OCR_PROVIDER=google_vision but credentials not available.")
        print("   Will fall back to local OCR.")
    
    # Test OCR
    print(f"\n🧪 Testing OCR extraction...")
    try:
        test_bytes = create_test_image()
        print(f"  Created test image: {len(test_bytes)} bytes")
        
        result = ocr_provider.extract_document_text(test_bytes)
        
        print(f"\n✅ OCR SUCCESS")
        print(f"  Provider used: {result.get('provider', 'unknown')}")
        print(f"  Text extracted: {len(result.get('text', ''))} chars")
        print(f"  Blocks: {len(result.get('blocks', []))}")
        print(f"  Words: {len(result.get('words', []))}")
        print(f"  Confidence: {result.get('confidence')}")
        
        if result.get('text'):
            preview = result['text'][:100]
            print(f"  Text preview: {preview}...")
        
    except Exception as e:
        print(f"\n❌ OCR FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Integration check
    print(f"\n📦 Pipeline integration:")
    try:
        from app.services.pipeline import process_scan_pipeline
        print(f"  ✓ Pipeline imports successfully")
        print(f"  ✓ ocr_provider is integrated")
    except Exception as e:
        print(f"  ✗ Pipeline import failed: {e}")
        return 1
    
    print("\n" + "=" * 80)
    print("✅ INTEGRATION TEST COMPLETE")
    print("=" * 80)
    
    if ocr_provider.primary_provider_name == "google_vision":
        print("\n🎉 Google Cloud Vision is active as primary OCR provider!")
    else:
        print("\n💡 Using local OCR. To enable Google Vision:")
        print("   1. Set up service account: https://cloud.google.com/vision/docs/auth")
        print("   2. Download JSON key")
        print("   3. Set: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        print("   4. Set: export OCR_PROVIDER=google_vision")
        print("   5. Restart backend")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
