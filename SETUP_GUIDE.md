# MedVault — Comprehensive Setup Guide

> Step-by-step instructions for local development, testing, and production deployment on Render + MongoDB Atlas.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [System Dependencies](#2-system-dependencies)
3. [Repository Setup](#3-repository-setup)
4. [MongoDB Atlas Setup](#4-mongodb-atlas-setup)
5. [Backend Configuration](#5-backend-configuration)
6. [Backend Startup](#6-backend-startup)
7. [Frontend Configuration](#7-frontend-configuration)
8. [Frontend Startup](#8-frontend-startup)
9. [Optional: Mistral AI API Key](#9-optional-mistral-ai-api-key)
10. [Optional: Browser Push Notifications (VAPID)](#10-optional-browser-push-notifications-vapid)
11. [Optional: Email (SMTP)](#11-optional-email-smtp)
12. [Verify the Full Stack](#12-verify-the-full-stack)
13. [Production Deployment (Render)](#13-production-deployment-render)
14. [Environment Variable Reference](#14-environment-variable-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python | 3.12 | Exact version match recommended |
| Node.js | 20 LTS or later | npm 10+ included |
| Git | Any recent | For cloning |
| Tesseract OCR | 5.x | System-level install (see Section 2) |
| Poppler utilities | Any recent | For PDF rasterization |

---

## 2. System Dependencies

### Windows (PowerShell, run as Administrator)

**Tesseract OCR:**
```powershell
# Option A: winget
winget install --id UB-Mannheim.TesseractOCR

# Option B: Chocolatey
choco install tesseract

# Option C: Manual
# Download from https://github.com/UB-Mannheim/tesseract/wiki
# Install to C:\Program Files\Tesseract-OCR\
# Add to PATH: C:\Program Files\Tesseract-OCR\
```

**Poppler (for PDF rendering):**
```powershell
# Option A: Chocolatey
choco install poppler

# Option B: Manual
# Download from https://github.com/oschwartz10612/poppler-windows/releases
# Extract to C:\poppler\
# Add C:\poppler\Library\bin to PATH
```

**Verify installations:**
```powershell
tesseract --version    # Should show 5.x
pdfinfo --version      # Should show poppler version
```

**Set TESSERACT_CMD in backend/.env (if not on PATH):**
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### macOS

```bash
brew install tesseract poppler
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils libzbar0 libgl1
```

---

## 3. Repository Setup

```powershell
# Clone the repository
git clone <your-repository-url>
cd "Medvault- Healthcare Document Privacy Pipeline Final Version"
```

---

## 4. MongoDB Atlas Setup

MedVault uses MongoDB Atlas M0 (free forever) as its database. Files are **never** stored here — only metadata.

### Create a Free Cluster

1. Go to [https://cloud.mongodb.com](https://cloud.mongodb.com) and create a free account
2. Click **Build a Database** → select **M0 Free** tier
3. Choose your cloud provider and region (any region)
4. Name your cluster (e.g., `medvault-cluster`)
5. Click **Create**

### Create a Database User

1. In Atlas sidebar, go to **Database Access** → **Add New Database User**
2. Choose **Password** authentication
3. Set username (e.g., `medvault`) and a strong password
4. Set **Built-in Role** to **Atlas admin** (or **Read and write to any database**)
5. Click **Add User**

### Whitelist Your IP

1. Go to **Network Access** → **Add IP Address**
2. For development: click **Allow Access from Anywhere** (`0.0.0.0/0`)
3. For production: add only your Render service's IP (or use `0.0.0.0/0` with a strong password)

### Get Your Connection String

1. Go to **Database** → **Connect** → **Connect your application**
2. Select **Python** driver, version **3.12 or later**
3. Copy the connection string:
   ```
   mongodb+srv://medvault:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
4. Replace `<password>` with your actual database user password

---

## 5. Backend Configuration

```powershell
cd backend
cp .env.example .env
```

Open `backend/.env` and fill in the required fields:

```env
# Required — MongoDB Atlas connection string
MONGODB_URI=mongodb+srv://medvault:<password>@cluster0.xxxxx.mongodb.net/

# Required — database name (default is fine)
MONGODB_DB_NAME=medvault

# Required — JWT secret (must be at least 32 characters)
# Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=your-super-secret-jwt-key-at-least-32-characters

# Optional — Mistral AI for ambiguity resolution and explainability
# App works fully without this; explanations use local template fallback
MISTRAL_API_KEY=

# Optional — VAPID keys for browser push notifications
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@yourdomain.com

# Optional — SMTP email for secure share notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com

# Frontend URL (for share link generation)
FRONTEND_PUBLIC_URL=http://127.0.0.1:5173

# Tesseract path (Windows only, if not on PATH)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Create and Activate Virtual Environment

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If execution policy blocks this, run first:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Install Python Dependencies

```powershell
pip install -r requirements.txt
```

> **Note:** The first install downloads three NLP model packages (spaCy `en_core_web_lg`, scispaCy `en_core_sci_md`, `en_ner_bc5cdr_md`). This may take several minutes and ~1GB of disk space.

---

## 6. Backend Startup

```powershell
# From the backend directory with .venv activated
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Expected output:**
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Verify:**
```powershell
# Should return {"status":"healthy","service":"MedVault API"}
Invoke-RestMethod http://127.0.0.1:8000/health

# Interactive API documentation
Start-Process "http://127.0.0.1:8000/docs"
```

---

## 7. Frontend Configuration

```powershell
cd frontend
npm install
cp .env.example .env
```

Open `frontend/.env` and set:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 8. Frontend Startup

```powershell
# From the frontend directory
npm run dev -- --host 127.0.0.1 --port 5173
```

**Expected output:**
```
  VITE v8.x  ready in xxx ms

  ➜  Local:   http://127.0.0.1:5173/
```

Open `http://127.0.0.1:5173` in your browser.

---

## 9. Optional: Mistral AI API Key

MedVault works fully without a Mistral API key. Without it, explanations use a local template-based fallback. With it, you get:
- More nuanced ambiguity resolution for mid-confidence PHI spans
- Richer plain-language redaction explanations

**Get a key:**
1. Go to [https://console.mistral.ai](https://console.mistral.ai)
2. Create an account and go to **API Keys**
3. Create a new key
4. Add to `backend/.env`:
   ```env
   MISTRAL_API_KEY=your-mistral-api-key-here
   ```

The model defaults to `mistral-small-latest`. Change to `mistral-large-latest` for higher accuracy at higher cost:
```env
MISTRAL_MODEL=mistral-large-latest
```

---

## 10. Optional: Browser Push Notifications (VAPID)

VAPID keys enable job-completion push notifications to the browser.

**Generate VAPID keys:**
```python
# Run in Python (with pywebpush installed):
from py_vapid import Vapid
vapid = Vapid()
vapid.generate_keys()
print("Public:", vapid.public_key.decode())
print("Private:", vapid.private_key.decode())
```

Or use an online generator (e.g., [https://vapidkeys.com](https://vapidkeys.com)).

Add to `backend/.env`:
```env
VAPID_PUBLIC_KEY=BFJ...your-public-key...
VAPID_PRIVATE_KEY=your-private-key...
VAPID_SUBJECT=mailto:admin@yourdomain.com
```

---

## 11. Optional: Email (SMTP)

Secure share links can be emailed to recipients. Configure SMTP for this feature.

**Gmail with App Password (recommended):**
1. Enable 2-Factor Authentication on your Gmail account
2. Go to Google Account → Security → App passwords
3. Create an app password for "Mail"
4. Add to `backend/.env`:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=your-16-char-app-password
   SMTP_FROM_EMAIL=your-email@gmail.com
   SMTP_USE_TLS=true
   ```

**Free SMTP alternatives:**
- Brevo (Sendinblue): 300 emails/day free
- Mailgun: 100 emails/day free
- Mailtrap: for testing only

---

## 12. Verify the Full Stack

After starting both backend and frontend:

1. Open `http://127.0.0.1:5173`
2. Navigate to **Create an account** and register with `admin@gmail.com` and `P@ssw0rd1234`
3. Sign in — the dashboard should open
4. Upload a file from `backend/sample_files/pdf/patient_portal_mode.pdf`
5. Select **Patient Portal** mode and start redaction
6. The capsule loader should appear, then the job should complete
7. Download the redacted file and verify PHI is replaced with `[REDACTED]`

See `MANUAL_TESTING_GUIDE.md` for the full end-to-end test checklist.

---

## 13. Production Deployment (Render)

### Backend on Render

1. Create a **New Web Service** on [https://render.com](https://render.com)
2. Connect your repository
3. Set **Language** to **Docker**
4. Set **Root Directory** to `backend`
5. Set **Dockerfile Path** to `Dockerfile` (relative to that root directory)
6. Leave Render's native **Build Command** and **Start Command** fields empty; the Dockerfile owns both steps
7. Add all environment variables from Section 14 to the Render **Environment** tab
8. Set `FRONTEND_PUBLIC_URL` to your actual Vercel/frontend domain

> **Important:** Render's free tier has a request timeout. Ensure `TEMP_JOB_DIR` is set to `/tmp/medvault_jobs` since Render's ephemeral filesystem is acceptable for process-and-discard files.

### Frontend on Vercel

1. Import your repository at [https://vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_BASE_URL=https://your-backend.onrender.com`
4. Deploy

### System Dependencies on Render

Render's native Python runtime does not install packages from `apt.txt`. Deploy the backend as a Docker web service using `backend/Dockerfile`; it installs the required system packages:
```
tesseract-ocr
poppler-utils
libgl1
libzbar0
```

---

## 14. Environment Variable Reference

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URI` | ✅ Yes | — | MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | No | `medvault` | Database name |
| `JWT_SECRET` | ✅ Yes | — | JWT signing secret (min 32 bytes) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token expiry in minutes |
| `MISTRAL_API_KEY` | No | — | Mistral AI API key (optional) |
| `MISTRAL_MODEL` | No | `mistral-small-latest` | Mistral model selection |
| `VAPID_PUBLIC_KEY` | No | — | VAPID public key for push |
| `VAPID_PRIVATE_KEY` | No | — | VAPID private key for push |
| `VAPID_SUBJECT` | No | — | VAPID subject (mailto:...) |
| `SMTP_HOST` | No | — | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASS` | No | — | SMTP password |
| `SMTP_FROM_EMAIL` | No | — | Sender email address |
| `SMTP_USE_TLS` | No | `true` | Use TLS for SMTP |
| `FRONTEND_PUBLIC_URL` | No | `http://127.0.0.1:5173` | Frontend URL for share links |
| `TESSERACT_CMD` | No | system PATH | Path to tesseract binary |
| `TEMP_JOB_DIR` | No | `./.medvault_jobs` | Temp directory for job files |
| `TEMP_JOB_TTL_SECONDS` | No | `3600` | File TTL before auto-cleanup |
| `TEMP_CLEANUP_INTERVAL_SECONDS` | No | `300` | Cleanup sweep interval |
| `MAX_UPLOAD_SIZE_BYTES` | No | `52428800` (50MB) | Max upload file size |
| `MAX_BATCH_FILES` | No | `25` | Max files per batch job |
| `MAX_CONCURRENT_CHUNKS` | No | `4` | Concurrent detection chunks |

### Frontend (`frontend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | ✅ Yes | — | Backend API base URL |

---

## 15. Troubleshooting

### "tesseract is not installed or not in your PATH"
Set `TESSERACT_CMD` in `backend/.env` to the full path:
```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### "MONGODB_URI must be a valid MongoDB connection URI"
Ensure the URI starts with `mongodb://` or `mongodb+srv://` and the password has been filled in (replace `<password>` in the Atlas connection string).

### "JWT_SECRET must contain at least 32 bytes"
Generate a secure secret:
```python
import secrets
print(secrets.token_urlsafe(48))
```

### NLP model download fails
The scispaCy models are downloaded directly from S3. If they time out, download manually and install:
```powershell
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz
```

### CORS errors in browser
Ensure `FRONTEND_PUBLIC_URL` or `CORS_ORIGINS` in `backend/.env` includes your frontend origin:
```env
CORS_ORIGINS=["http://127.0.0.1:5173","http://localhost:5173"]
```

### Redaction job stays at "processing" indefinitely
Check the uvicorn terminal for Python tracebacks. Common causes:
- Missing system dependency (Tesseract, Poppler)
- MongoDB connection error
- Out of memory (large documents on Render free tier)

### Push notifications not appearing
Browser push requires HTTPS in production. In local development, `localhost` is treated as secure context. Ensure VAPID keys are correctly configured and the browser has granted notification permission in Settings.

---

*For the full end-to-end test procedure, see `MANUAL_TESTING_GUIDE.md`.*
