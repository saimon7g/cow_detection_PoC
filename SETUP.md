# Setup Guide

Complete guide to install, configure, and run the Cow Insurance Management system.

---

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

---

## Step 1: Clone / Navigate to the Project

```bash
cd cow_detection_PoC
```

---

## Step 2: Create a Virtual Environment

```bash
python3 -m venv venv
```

---

## Step 3: Activate the Virtual Environment

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

---

## Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Dependencies installed:
- Django & Django REST Framework
- djangorestframework-simplejwt (JWT authentication)
- drf-spectacular (OpenAPI / Swagger UI docs)
- django-cors-headers
- PyTorch & torchvision (ML model)
- matplotlib, scikit-learn

---

## Step 5: Set Up the Database

```bash
cd cow_detection_backend
python manage.py makemigrations
python manage.py migrate
```

This creates a fresh SQLite database with all required tables.

---

## Step 6: Create the Initial Users

The system has three roles: **admin**, **company agent**, and **farmer**.  
Admins and company agents cannot self-register — they must be created manually or by a higher-level user.

Use the Django shell to bootstrap the first admin and company agent.  
**Safe to run multiple times** — if a user already exists, they are updated; otherwise they are created.

```bash
python manage.py shell -c "
from django.contrib.auth.models import User
from api.models import UserProfile

# Admin: create if missing, ensure profile
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={'email': 'admin@example.com', 'is_superuser': True, 'is_staff': True}
)
if created:
    admin.set_password('adminpass123')
    admin.save()
profile, _ = UserProfile.objects.get_or_create(user=admin, defaults={'user_type': 'admin'})
if profile.user_type != 'admin':
    profile.user_type = 'admin'
    profile.save()
print('Admin OK')

# Company agent: create if missing, ensure profile
agent, created = User.objects.get_or_create(
    username='agent1',
    defaults={'email': 'agent@company.com'}
)
if created:
    agent.set_password('agentpass123')
    agent.save()
profile, _ = UserProfile.objects.get_or_create(user=agent, defaults={'user_type': 'company_agent'})
if profile.user_type != 'company_agent':
    profile.user_type = 'company_agent'
    profile.save()
print('Agent OK')
print('Done.')
"
```

After that, company agents create farmer accounts through the API. See the [User Guide](README.md) for the workflow.

---

## Step 7: Run the Server

```bash
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/`

---

## Quick Start (All Commands at Once)

```bash
# From project root
source venv/bin/activate
pip install -r requirements.txt

cd cow_detection_backend
python manage.py makemigrations
python manage.py migrate

# Bootstrap admin + first agent (safe to re-run; uses get_or_create)
python manage.py shell -c "
from django.contrib.auth.models import User
from api.models import UserProfile
admin, c = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_superuser': True, 'is_staff': True})
if c: admin.set_password('adminpass123'); admin.save()
UserProfile.objects.get_or_create(user=admin, defaults={'user_type': 'admin'})
agent, c = User.objects.get_or_create(username='agent1', defaults={'email': 'agent@company.com'})
if c: agent.set_password('agentpass123'); agent.save()
UserProfile.objects.get_or_create(user=agent, defaults={'user_type': 'company_agent'})
"

python manage.py runserver
```

---

## Authentication

All API endpoints require a **JWT token** in the request header:

```
Authorization: Bearer <access_token>
```

Obtain a token by posting credentials to:

```
POST /api/token/
Body: { "username": "...", "password": "..." }
```

The response includes the token and the user's role (`user_type`).

For complete API reference, see [`cow_detection_backend/API_DOCUMENTATION.md`](cow_detection_backend/API_DOCUMENTATION.md).

---

## Access Points

Once the server is running:

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/api/` | REST API base |
| `http://127.0.0.1:8000/api/token/` | Login (get JWT) |
| `http://127.0.0.1:8000/api/docs/` | Swagger UI (interactive API docs, try requests, copy cURL) |
| `http://127.0.0.1:8000/api/redoc/` | ReDoc (API reference) |
| `http://127.0.0.1:8000/api/schema/` | OpenAPI 3 schema (for Postman import) |
| `http://127.0.0.1:8000/admin/` | Django admin panel (superuser only) |

---

## Project Structure

```
cow_detection_PoC/
├── venv/                          # Virtual environment
├── cow_detection_backend/         # Django backend
│   ├── manage.py
│   ├── db.sqlite3                 # SQLite database (after migrate)
│   ├── media/                     # Uploaded photos (auto-created)
│   │   └── cow_images/
│   ├── cow_detection_backend/     # Django project settings & URLs
│   ├── api/                       # API app (models, views, serializers)
│   │   ├── models.py              # UserProfile, CowProfile, InsuranceClaim, ...
│   │   ├── views.py               # Endpoint logic
│   │   ├── serializers.py         # Request/response formatting
│   │   ├── permissions.py         # Role-based permission classes
│   │   ├── urls.py                # URL routing
│   │   └── migrations/            # Database migrations
│   └── API_DOCUMENTATION.md       # Full API reference
├── incremental_train.py           # Standalone ML training script
├── contrastive_autoencoder.py     # ML model definition
├── cae_checkpoint.pt              # Trained model checkpoint
├── training_metrics.json          # Training metrics history
├── plots/                         # Embedding visualizations
├── requirements.txt               # Python dependencies
├── README.md                      # User guide
└── SETUP.md                       # This file
```

---

## Troubleshooting

**Port already in use:**
```bash
python manage.py runserver 8001
# or
kill -9 $(lsof -ti:8000)
```

**Database errors:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Module not found / import errors:**
```bash
# Make sure venv is activated
source venv/bin/activate
pip install -r requirements.txt
```

**401 Unauthorized on API calls:**  
Include the `Authorization: Bearer <token>` header. Tokens expire after 24 hours; use `/api/token/refresh/` to get a new access token.

**403 Forbidden on API calls:**  
The endpoint requires a different role. Check which role is allowed in `API_DOCUMENTATION.md`.
