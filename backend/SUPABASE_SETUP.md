# Supabase Setup Guide

This project uses **Supabase** (PostgreSQL cloud database) instead of local PostgreSQL. Follow these steps to set up and run the backend locally.

## Prerequisites

- Python 3.8+
- A Supabase account (free tier available at https://supabase.com)

## Step 1: Create a Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign up or log in
3. Click "New project"
4. Choose a name (e.g., `border-screening`)
5. Set a strong database password
6. Select a region close to you
7. Click "Create new project" and wait for setup (~2 minutes)

## Step 2: Get Your Connection String

1. In your Supabase project, go to **Settings > Database**
2. Under "Connection string", select **PostgreSQL**
3. Copy the connection string (it looks like):
   ```
   postgresql://postgres:[YOUR_PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
   ```
4. Replace `[YOUR_PASSWORD]` with the password you set during project creation

## Step 3: Configure Environment Variables

1. Open `.env` in the backend directory:
   ```bash
   cd backend
   ```

2. Update the `DATABASE_URL` with your Supabase connection string:
   ```env
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
   SECRET_KEY=your-secret-key-generate-a-random-one
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=120
   CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
   UPLOAD_DIR=./uploads
   ```

## Step 4: Install Dependencies

```bash
python3 -m pip install --user -r requirements.txt
```

## Step 5: Initialize Database Schema

Run the database creation script:

```bash
python3 create_db.py
```

(This will create the necessary tables in your Supabase database)

## Step 6: Run the Backend Server

Start the FastAPI server:

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### Connection Refused
- Verify your Supabase connection string is correct
- Check that you're using the PostgreSQL connection string (not the HTTP one)

### "Database does not exist" Error
- Run `python3 create_db.py` to initialize the schema

### Timeout Issues
- Supabase free tier may have some latency
- Check your internet connection
- Verify Supabase project is running (check dashboard)

### CORS Errors
- Make sure your frontend URL is in the `CORS_ORIGINS` environment variable
- Separate multiple origins with commas

## Running Locally with Frontend

If you have a frontend running on `http://localhost:3000` or `http://localhost:5173`:

1. Ensure both URLs are in `CORS_ORIGINS`
2. The backend will accept requests from both addresses

## Helpful Links

- Supabase Docs: https://supabase.com/docs
- PostgreSQL Connection String Format: https://www.postgresql.org/docs/current/libpq-connect-string.html
- FastAPI Docs: https://fastapi.tiangolo.com/
