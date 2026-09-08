# Setup Checklist - Border Document Screening

## Quick Start Guide

### Prerequisites ✓
- [x] Python 3.8+ installed
- [x] Dependencies installed
- [ ] Supabase account created

### Supabase Configuration (DO THIS FIRST)
- [ ] Create Supabase account at https://supabase.com
- [ ] Create new project named "border-screening"
- [ ] Set database password and note it
- [ ] Go to Settings > Database
- [ ] Copy PostgreSQL connection string
- [ ] Note the format: `postgresql://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres`

### Environment Setup
- [ ] Open `/backend/.env` file
- [ ] Replace `DATABASE_URL` with your Supabase connection string
- [ ] Replace `[YOUR_SUPABASE_PASSWORD]` with actual password
- [ ] Replace `[YOUR_SUPABASE_PROJECT_ID]` with actual project ID
- [ ] Save the file

### Run Backend Locally

**Option 1: Automated (Recommended)**
```bash
cd /Users/ravib/Desktop/SIH/sih/backend
./run_local.sh
```

**Option 2: Manual**
```bash
cd /Users/ravib/Desktop/SIH/sih/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Verify It's Working
- [ ] Server starts without errors
- [ ] Open http://localhost:8000/docs in browser
- [ ] See Swagger UI documentation
- [ ] Try a test endpoint (e.g., GET /api/v1/health)

### Files Created/Modified
- ✓ `/backend/.env` - Environment variables with Supabase URL
- ✓ `/backend/.env.example` - Updated template for Supabase
- ✓ `/backend/requirements.txt` - Updated with psycopg (PostgreSQL driver)
- ✓ `/backend/SUPABASE_SETUP.md` - Detailed Supabase setup guide
- ✓ `/backend/run_local.sh` - Quick start script
- ✓ `/backend/README_LOCAL_SETUP.md` - Setup instructions
- ✓ `/SETUP_CHECKLIST.md` - This file

### Database Initialization (Optional)
If you need to initialize the database schema:
```bash
python3 create_db.py
```

## Support Resources

1. **Supabase Setup Details**: See `backend/SUPABASE_SETUP.md`
2. **API Documentation**: http://localhost:8000/docs (when running)
3. **Troubleshooting**: See "Troubleshooting" section in `SUPABASE_SETUP.md`

## Environment Variables Explained

```env
DATABASE_URL              # Supabase PostgreSQL connection string
SECRET_KEY               # JWT signing key (change in production!)
ALGORITHM                # JWT algorithm (HS256)
ACCESS_TOKEN_EXPIRE_MINUTES  # Token expiry time
CORS_ORIGINS             # Allowed frontend URLs
UPLOAD_DIR              # Directory for uploaded documents
```

## Frontend Setup (If Needed)

If you have a frontend, make sure it's included in `CORS_ORIGINS`:
- For React dev server on port 3000: include `http://localhost:3000`
- For Vite dev server on port 5173: include `http://localhost:5173`

The `.env` file already includes both.

---

**Status**: Ready to configure Supabase and run locally! 🚀
