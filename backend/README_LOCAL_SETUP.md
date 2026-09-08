# Border Document Screening API - Local Setup

## ✅ Completed Setup Steps

- ✓ Python dependencies installed
- ✓ Environment file template created  
- ✓ Supabase setup guide created
- ✓ Run script generated

## ⚠️ Next Steps (Required)

### 1. Create Supabase Project

- Go to https://supabase.com
- Sign up/login
- Create new project (name: "border-screening")
- Note your database password

### 2. Get Your Connection String

- In Supabase dashboard: Settings > Database
- Copy PostgreSQL connection string format:
  ```
  postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
  ```

### 3. Update .env File

Open `backend/.env` and replace the DATABASE_URL:

```env
DATABASE_URL=postgresql://postgres:MyPassword123@db.abc123xyz.supabase.co:5432/postgres
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
UPLOAD_DIR=./uploads
```

### 4. Run the Server

**Option A: Using shell script**
```bash
cd backend
./run_local.sh
```

**Option B: Manual run**
```bash
cd backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the API

- Open browser: http://localhost:8000/docs
- You should see the Swagger UI with all endpoints

## 📖 Detailed Guide

See `backend/SUPABASE_SETUP.md` for complete instructions including troubleshooting.

## 🔗 Useful Links

- Supabase: https://supabase.com
- FastAPI Docs: http://localhost:8000/docs (when running)
- Project Directory: `/Users/ravib/Desktop/SIH/sih/`

## ❓ Troubleshooting

Check `SUPABASE_SETUP.md` under "Troubleshooting" section for common issues.
