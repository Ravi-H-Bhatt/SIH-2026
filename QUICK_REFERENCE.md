# ⚡ QUICK REFERENCE - Local Development

## 🎯 START HERE

Your system is running! Access it here:

| What | URL | What to do |
|------|-----|-----------|
| **Web App** | http://localhost:3000 | Click "Demo Mode" to login |
| **API Docs** | http://localhost:8000/docs | Explore API endpoints |
| **API Root** | http://localhost:8000 | Check API status |

---

## 🔄 COMMANDS CHEAT SHEET

### Start Services (After First Setup)

```bash
# Terminal 1 - Backend
cd /Users/ravib/Desktop/SIH/sih/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend  
cd /Users/ravib/Desktop/SIH/sih/frontend
npm run dev
```

### Stop Services
```bash
# Backend: Ctrl+C in backend terminal
# Frontend: Ctrl+C in frontend terminal
# Or kill ports:
kill $(lsof -t -i:8000)  # Kill backend
kill $(lsof -t -i:3000)  # Kill frontend
```

### Restart Services
```bash
# Just Ctrl+C and restart with commands above
```

---

## 🧪 TEST FEATURES

### Via Frontend (http://localhost:3000)
1. **New Screening** - Upload document + face image
2. **Scan History** - View past screenings
3. **Dashboard** - See statistics & trends
4. **User Management** - Manage users (admin only)

### Via API (http://localhost:8000/docs)
1. **Health Check** - `GET /api/v1/health`
2. **Create Scan** - `POST /api/v1/scans`
3. **Get Results** - `GET /api/v1/scans/{id}`
4. **List Scans** - `GET /api/v1/scans`

---

## 📊 EXPECTED RESULTS

### When you upload images:
- ✅ Document recognized
- ✅ OCR extracts text
- ✅ Face detected
- ✅ Risk score calculated
- ✅ Evidence shown

### Database:
- ✅ Data saved locally (SQLite)
- ✅ Audit logs recorded
- ✅ Results persistent

---

## 🔐 AUTH STATUS

**Currently**: Bypass enabled (`BYPASS_AUTH=true`)
- You can access without login
- Click "Demo Mode" or use any credentials

**For Production**: Set `BYPASS_AUTH=false` and use:
- Email: `admin@borderscreening.gov.in`
- Password: `change_me_123`

---

## 💾 DATA LOCATION

```
Backend database:
/Users/ravib/Desktop/SIH/sih/backend/border_screening.db

Uploads:
/Users/ravib/Desktop/SIH/sih/backend/uploads/

Logs:
Check terminal output
```

---

## 🐛 QUICK FIXES

| Problem | Fix |
|---------|-----|
| Port 8000 in use | `kill $(lsof -t -i:8000)` |
| Port 3000 in use | `kill $(lsof -t -i:3000)` |
| Module not found | `pip3 install -r requirements.txt` |
| npm issues | `npm cache clean --force && npm install` |
| Disk full | Delete cache: `rm -rf ~/.npm && npm cache clean --force` |

---

## 📈 ARCHITECTURE

```
Frontend (Next.js)
   ↓ HTTP/WebSocket
Backend API (FastAPI)
   ↓ SQL
Database (SQLite)

ML Pipeline:
- OCR (PaddleOCR) ✅
- Face (InsightFace) ✅
- Forgery (ELA) ✅
- Risk Scoring ✅
```

---

## ✨ KEY FILES

| File | Purpose |
|------|---------|
| `backend/main.py` | API entry point |
| `frontend/package.json` | Node dependencies |
| `backend/.env` | Backend config |
| `frontend/.env.local` | Frontend config |
| `supabase_schema.sql` | Database schema |

---

## 🚀 NEXT STEPS

1. ✅ **Running Locally** - DONE!
2. 📝 Test the system with sample images
3. 🔧 Configure Supabase (optional, for prod)
4. 📊 Review ML results & accuracy
5. 🎨 Customize UI branding
6. 🌐 Deploy to production

---

## 📞 HELP

- Backend issues? Check: `backend/.env`
- Frontend issues? Check: `frontend/.env.local`
- Database issues? Check: `supabase_schema.sql`
- API issues? Check: `http://localhost:8000/docs`

**Status**: ✅ All systems operational!

