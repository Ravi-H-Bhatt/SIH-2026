# Google Cloud Vision API — Quick Setup

## Purpose

Google Cloud Vision provides enterprise-grade OCR for document text extraction in the SIH 26188 pipeline.

**Vision handles:** Text extraction, bounding boxes, confidence scores  
**Vision does NOT replace:** MRZ validation, forensics, face verification, identity matching, risk scoring

## Architecture

```
Camera/Upload → Supabase Storage → FastAPI → Google Vision OCR
→ text/coordinates → MRZ parser → validation → forensics → face → identity → risk
```

## Setup Steps

### 1. Enable Cloud Vision API

```bash
# Open Google Cloud Console
https://console.cloud.google.com/apis/library/vision.googleapis.com

# Click "Enable"
```

### 2. Create Service Account

```bash
# Console → IAM & Admin → Service Accounts → Create
# Name: sih-vision-ocr
# Role: Cloud Vision API User
# Create JSON key → Download
```

### 3. Configure Backend

```bash
cd backend

# Set credentials path (absolute path required)
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/key.json"

# Enable Vision as primary OCR
export OCR_PROVIDER=google_vision

# Or add to .env:
echo "GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/key.json" >> .env
echo "OCR_PROVIDER=google_vision" >> .env
echo "OCR_FALLBACK_ENABLED=true" >> .env
```

### 4. Install SDK

```bash
pip install google-cloud-vision==3.7.2 google-auth==2.29.0
```

### 5. Test Integration

```bash
python3 scripts/test_google_vision_integration.py
```

Expected output:
```
✅ INTEGRATION TEST COMPLETE
🎉 Google Cloud Vision is active as primary OCR provider!
```

### 6. Restart Backend

```bash
uvicorn main:app --reload
```

## Environment Variables (Backend Only)

```bash
# Required
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
OCR_PROVIDER=google_vision

# Optional
GOOGLE_CLOUD_PROJECT_ID=your-project-id
OCR_FALLBACK_ENABLED=true
VISION_MAX_IMAGE_BYTES=10485760
VISION_REQUEST_TIMEOUT_SECONDS=30
VISION_MAX_RETRIES=2
```

## Security Rules

❌ **NEVER:**
- Commit service-account JSON to Git
- Expose credentials to browser/Next.js (no `NEXT_PUBLIC_*`)
- Send continuous camera frames to Vision API
- Hardcode API keys in source code

✅ **ALWAYS:**
- Use service account / ADC for production
- Store credentials server-side only
- Enable fallback to local OCR
- Log Vision usage for cost control

## Cost Control

- Only send captured/uploaded images (not live video frames)
- Images > 10 MB are rejected before API call
- Automatic retry with exponential backoff
- Fallback to free local OCR on failure
- Log all Vision requests for billing visibility

## Production Deployment

For Vercel (frontend) + FastAPI backend:

1. **Frontend (.env.local):**
   ```bash
   NEXT_PUBLIC_SUPABASE_URL=https://...
   NEXT_PUBLIC_SUPABASE_ANON_KEY=...
   NEXT_PUBLIC_API_BASE_URL=https://your-api.com
   ```

2. **Backend (server secrets):**
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
   OCR_PROVIDER=google_vision
   ```

Never upload service-account JSON to Vercel. Use platform secret management.

## API Key Mode (Testing Only)

```bash
# Console → APIs & Services → Credentials → Create API Key
# Restrict to: Cloud Vision API

export GOOGLE_VISION_API_KEY=AIza...
export OCR_PROVIDER=google_vision
```

⚠️ Service account / ADC is strongly preferred over API key.

## Troubleshooting

**"Google Vision unavailable"**
- Check: `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON
- Check: JSON file has correct IAM permissions
- Check: Vision API is enabled in GCP project
- Check: Service account has "Cloud Vision API User" role

**"quota exceeded"**
- Check: billing enabled on GCP project
- Check: Vision API quota limits
- Enable: `OCR_FALLBACK_ENABLED=true`

**"No text detected"**
- Check: image quality (blur, lighting, contrast)
- Check: image format (JPEG/PNG supported)
- Check: text is visible and not occluded

## Verification

```bash
# Check configuration
python3 -c "from app.core.config import settings; print(f'Provider: {settings.OCR_PROVIDER}'); print(f'Configured: {settings.google_vision_configured}')"

# Check provider
python3 -c "from app.services.google_vision import ocr_provider; print(f'Primary: {ocr_provider.primary_provider_name}')"

# Run integration test
python3 scripts/test_google_vision_integration.py
```

## Files Modified

- `backend/app/services/google_vision.py` — Vision service + provider abstraction
- `backend/app/services/pipeline.py` — integrated Vision into scan pipeline
- `backend/app/core/config.py` — added Vision env vars
- `backend/.env.example` — documented Vision configuration
- `backend/requirements.txt` — added google-cloud-vision
- `.gitignore` — protect credentials
- `tests/test_google_vision.py` — unit tests with mocks
- `scripts/test_google_vision_integration.py` — validation script
- `SIH26188_MASTER_AGENT_PROMPT.md` — updated architecture

## Support

Vision API docs: https://cloud.google.com/vision/docs  
OCR guide: https://cloud.google.com/vision/docs/ocr  
Authentication: https://cloud.google.com/vision/docs/auth  
Pricing: https://cloud.google.com/vision/pricing
