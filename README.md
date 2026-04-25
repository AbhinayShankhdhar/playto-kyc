# Playto KYC Pipeline

Full-stack KYC onboarding system for Playto Pay. Built with Django + DRF (backend) and React + Tailwind (frontend).

## Features

- Multi-step KYC form with save-and-resume
- Enforced state machine (illegal transitions → 400)
- File upload validation (PDF/JPG/PNG, max 5 MB)
- Reviewer dashboard with SLA tracking (>24h = at_risk)
- Merchant isolation (Merchant A cannot see Merchant B's data)
- Notification event log on every state change

---

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- pip

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Seed test data
python manage.py shell < seed.py

# Start server
python manage.py runserver
```

Backend runs at: http://localhost:8000

### Frontend

```bash
cd frontend

# Install
npm install

# Start
npm start
```

Frontend runs at: http://localhost:3000

---

## Demo Credentials (after running seed)

| Role     | Username         | Password     |
|----------|------------------|--------------|
| Reviewer | reviewer1        | reviewer123  |
| Merchant | merchant_draft   | merchant123  |
| Merchant | merchant_review  | merchant123  |

---

## Running Tests

```bash
cd backend
python manage.py test kyc_app
```

---

## API Reference

All endpoints under `/api/v1/`

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Register user |
| POST | `/auth/login/` | Get token |
| GET  | `/auth/me/` | Current user info |

### Merchant
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/submissions/` | List / create submissions |
| GET/PATCH | `/submissions/<id>/` | View / update draft |
| POST | `/submissions/<id>/submit/` | Submit for review |
| POST | `/submissions/<id>/documents/<type>/` | Upload doc (pan/aadhaar/bank_statement) |

### Reviewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reviewer/queue/` | Queue (oldest first) |
| GET | `/reviewer/metrics/` | Dashboard metrics |
| GET | `/reviewer/submissions/<id>/` | Full submission detail |
| POST | `/reviewer/submissions/<id>/transition/` | Change state |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications/` | Merchant's notification log |

---

## State Machine

```
draft → submitted → under_review → approved (terminal)
                                 → rejected (terminal)
                                 → more_info_requested → submitted (loop)
```

---

## Deployment (Render)

1. Create a new Web Service on Render, connect GitHub repo
2. Backend:
   - Build: `pip install -r requirements.txt && python manage.py migrate`
   - Start: `gunicorn kyc_project.wsgi`
   - Env vars: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=your-app.onrender.com`
3. Frontend:
   - Build: `npm run build`
   - `REACT_APP_API_URL=https://your-backend.onrender.com/api/v1`
