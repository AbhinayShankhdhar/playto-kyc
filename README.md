# Playto KYC Pipeline

KYC onboarding system for Playto Pay — merchants submit verification documents, reviewers approve/reject via a queue dashboard.

## Stack
- **Backend:** Django 4.2 + DRF, SQLite (dev) / PostgreSQL (prod)
- **Frontend:** React + Vite + Tailwind CSS (served from Django in prod)
- **Auth:** DRF Token Authentication

---

## Local Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python seed.py
python manage.py runserver
# → http://localhost:8000
```

### Frontend (dev mode)
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Run Tests
```bash
cd backend
python manage.py test kyc --verbosity=2
# Runs 12 tests — state machine + auth isolation
```

---

## Deploy to Railway (Recommended)

1. Push repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Set these environment variables in Railway dashboard:
   ```
   SECRET_KEY=<generate a random 50-char string>
   DEBUG=False
   ALLOWED_HOSTS=.railway.app
   DATABASE_URL=<Railway auto-fills this if you add a Postgres plugin>
   ```
4. Railway will auto-detect `nixpacks.toml` and:
   - Install Python deps + build React
   - Run `migrate` + `seed.py` + `collectstatic` (via Procfile release phase)
   - Start gunicorn
5. Frontend is served by Django from `frontend/dist/`

## Deploy to Render

1. Push to GitHub
2. New Web Service → connect repo
3. Build Command: `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build`
4. Start Command: `cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
5. Add env vars: `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL` (add a Postgres database)

---

## Demo Credentials

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Reviewer | `reviewer1` | `reviewer123` | Full queue + approve/reject |
| Merchant | `merchant_arjun` | `merchant123` | Draft submission — can edit & submit |
| Merchant | `merchant_priya` | `merchant123` | Under review, **SLA at risk ⚠️** |

---

## API Reference (all under `/api/v1/`)

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Register (role: merchant/reviewer) |
| POST | `/auth/login/` | Login → returns token |
| GET | `/auth/me/` | Current user info |

### Merchant
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/merchant/submissions/` | My submissions only |
| POST | `/merchant/submissions/` | Create new draft |
| GET | `/merchant/submissions/:id/` | View own submission |
| PATCH | `/merchant/submissions/:id/` | Edit (only draft/more_info_requested) |
| POST | `/merchant/submissions/:id/submit/` | Submit KYC |

### Reviewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reviewer/queue/` | Active queue, oldest first |
| GET | `/reviewer/submissions/` | All submissions |
| GET | `/reviewer/submissions/:id/` | Submission detail |
| POST | `/reviewer/submissions/:id/transition/` | Change state |
| GET | `/reviewer/metrics/` | Dashboard metrics |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications/` | Notification event log |

---

## State Machine

```
draft ──→ submitted ──→ under_review ──→ approved
                                    ├──→ rejected
                                    └──→ more_info_requested ──→ submitted (loop)
```

Illegal transitions return HTTP 400 with a descriptive error. State logic lives entirely in `kyc/models.py::KYCState`.

## File Upload Rules
- Accepted: `.pdf`, `.jpg`, `.jpeg`, `.png`
- Max size: **5 MB** — validated server-side, extension check
- Returns 400 with clear message on violation

## SLA Tracking
Submissions in queue > 24 hours: `is_at_risk: true` — computed dynamically from `submitted_at`, never stored as a stale flag.

---

## Project Structure

```
playto-kyc/
├── backend/
│   ├── kyc/
│   │   ├── models.py        # KYCState machine + all models
│   │   ├── views.py         # API views
│   │   ├── serializers.py   # DRF serializers + DocumentField validation
│   │   ├── permissions.py   # IsMerchant, IsReviewer
│   │   ├── urls.py          # All routes
│   │   └── tests.py         # 12 tests
│   ├── config/
│   │   ├── settings.py      # Env-aware settings (SQLite/Postgres)
│   │   └── urls.py          # Serves React build + API
│   ├── requirements.txt
│   └── seed.py              # Idempotent seed
├── frontend/
│   └── src/
│       ├── App.jsx           # Full UI (auth, merchant flow, reviewer dashboard)
│       └── api.js            # Typed API client
├── nixpacks.toml             # Railway build config
├── Procfile                  # Railway start + release commands
├── render.yaml               # Render.com config
├── README.md
└── EXPLAINER.md
```
