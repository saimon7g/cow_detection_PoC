# Cow Detection API Documentation

## Interactive docs (Swagger / ReDoc)

When the server is running, you can use:

| URL | Description |
|-----|-------------|
| **https://127.0.0.1:8000/api/docs/** | **Swagger UI** — browse endpoints, try requests, copy as cURL, use in Postman |
| **https://127.0.0.1:8000/api/redoc/** | **ReDoc** — read-only API reference |
| **https://127.0.0.1:8000/api/schema/** | **OpenAPI 3 schema** (YAML) — import into Postman or other tools |

In Swagger UI, click **Authorize**, then enter your JWT as `Bearer <access_token>` (or just the token) so authenticated requests work.

---

## Overview

This API supports three user roles:

| Role | Key capabilities |
|------|-----------------|
| **company_agent** | Create farmer accounts; register cows under a farmer; create insurance claims; verify claims (when assigned by admin). |
| **farmer** | View their own cows; create insurance claims for their own cows. |
| **admin** | Assign agents to verify claims; final approve/reject claims; view all data. |

---

## Authentication

All endpoints (except `POST /api/login/` and `POST /api/login/refresh/`) require a valid JWT in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

### Login

**POST** `/api/login/`

Obtain a JWT access + refresh token pair.

**Request (JSON):**
```json
{
  "username": "agent1",
  "password": "secret123"
}
```

**Response:**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user_type": "company_agent",
  "user_id": 1,
  "username": "agent1"
}
```

`user_type` is one of: `company_agent`, `farmer`, `admin`.

---

### Refresh Token

**POST** `/api/login/refresh/`

**Request (JSON):**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response:**
```json
{ "access": "<new_jwt_access_token>" }
```

---

## User Info

**GET** `/api/user/`
*Roles: all authenticated users*

Returns the authenticated user's profile.

**Response:**
```json
{
  "id": 1,
  "username": "agent1",
  "email": "agent@example.com",
  "first_name": "Ali",
  "last_name": "Khan",
  "date_joined": "2026-01-01T00:00:00Z",
  "user_type": "company_agent"
}
```

---

## Farmer Management

### Create Farmer

**POST** `/api/farmers/`
*Roles: company_agent only*

Company agent creates a new farmer account.

**Request (JSON):**
```json
{
  "username": "farmer_john",
  "email": "john@farm.com",
  "password": "password123",
  "password_confirm": "password123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201):**
```json
{
  "message": "Farmer created successfully.",
  "farmer": {
    "id": 5,
    "username": "farmer_john",
    "email": "john@farm.com",
    "first_name": "John",
    "last_name": "Doe",
    "date_joined": "2026-03-07T10:00:00Z",
    "user_type": "farmer"
  }
}
```

---

### List Farmers (Agent View)

**GET** `/api/farmers/list/`
*Roles: company_agent only*

Returns all farmers with their cow count.

**Response:**
```json
{
  "count": 2,
  "farmers": [
    {
      "id": 5,
      "username": "farmer_john",
      "email": "john@farm.com",
      "first_name": "John",
      "last_name": "Doe",
      "date_joined": "2026-03-07T10:00:00Z",
      "user_type": "farmer",
      "cow_count": 3
    }
  ]
}
```

---

## Cow Registration

### Register a Cow

**POST** `/api/register/`
*Roles: company_agent only*

Register a cow under a specific farmer. The farmer must already have an account.

**Content-Type:** `multipart/form-data`

**Required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner_id` | integer | User ID of the farmer who owns this cow |
| `cow_name` | string | Name of the cow |
| `muzzle_photos` | file(s) | Required when `train_model=true` |

**Optional fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cow_age` | integer | – | Age in months/years |
| `cow_breed` | string | – | Breed |
| `owner_name` | string | – | Display name for owner |
| `cow_photos` | file(s) | – | General photos (not used for training) |
| `train_model` | boolean | true | Trigger background ML training |
| `epochs` | integer | 50 | Training epochs |
| `batch_size` | integer | 8 | Training batch size |
| `contrastive_weight` | float | 0.8 | Contrastive loss weight |

**cURL example:**
```bash
curl -X POST https://127.0.0.1:8000/api/register/ \
  -H "Authorization: Bearer <agent_token>" \
  -F "owner_id=5" \
  -F "cow_name=Bella" \
  -F "cow_breed=Holstein" \
  -F "muzzle_photos=@muzzle1.jpg" \
  -F "train_model=true"
```

**Response (201):**
```json
{
  "message": "Cow registered successfully.",
  "cow_profile": {
    "id": 1,
    "policy_id": "POL-20260307-101500-A1B2C3D4",
    "cow_name": "Bella",
    "cow_age": null,
    "cow_breed": "Holstein",
    "owner_name": "John Doe",
    "cow_id": "COW-20260307-101500-E5F6G7H8",
    "created_at": "2026-03-07T10:15:00Z",
    "updated_at": "2026-03-07T10:15:00Z",
    "notes": "",
    "farmer_username": "farmer_john"
  },
  "farmer": { "id": 5, "username": "farmer_john", ... },
  "photos": { "cow_photos_saved": 0, "muzzle_photos_saved": 1 },
  "training": {
    "status": "started",
    "training_status_id": 1,
    "check_status_url": "/api/training-status/1/"
  }
}
```

---

### Training Status

**GET** `/api/training-status/<id>/`
*Roles: all authenticated users*

**Response:**
```json
{
  "id": 1,
  "status": "completed",
  "started_at": "...",
  "completed_at": "...",
  "num_images": 5,
  "epochs": 50,
  "checkpoint_path": "/path/to/checkpoint.pt"
}
```

`status` values: `pending`, `running`, `completed`, `failed`.

---

### List All Cow Profiles

**GET** `/api/profiles/`
*Roles: company_agent, admin*

Returns all registered cow profiles.

**Response:**
```json
{
  "count": 10,
  "profiles": [
    {
      "id": 1,
      "cow_name": "Bella",
      "cow_breed": "Holstein",
      "owner_name": "John Doe",
      "policy_id": "POL-20260307-101500-A1B2C3D4",
      "cow_id": "COW-20260307-101500-E5F6G7H8",
      "farmer_username": "farmer_john"
    }
  ]
}
```

---

### My Cows (Farmer)

**GET** `/api/my-cows/`
*Roles: farmer only*

Returns only the cows registered under the authenticated farmer.

**Response:**
```json
{
  "count": 2,
  "cows": [
    {
      "id": 1,
      "policy_id": "POL-...",
      "cow_name": "Bella",
      "cow_age": 24,
      "cow_breed": "Holstein",
      "owner_name": "John Doe",
      "cow_id": "COW-...",
      "created_at": "...",
      "updated_at": "...",
      "notes": "",
      "farmer_username": "farmer_john"
    }
  ]
}
```

---

## Cow Classification (ML)

**POST** `/api/classify/`
*Roles: company_agent, admin*

Identify a cow from a photo using the trained model.

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | file | yes | Cow image to classify |
| `top_k` | integer | no (default 5) | Number of top matches |
| `threshold` | float | no | Max distance threshold |

**Response:**
```json
{
  "message": "Classification completed successfully.",
  "verdict": {
    "matched": true,
    "best_match": { "cow_name": "Bella", "distance": 0.32, "rank": 1, "cow_profile": {...} },
    "confidence": "high"
  },
  "all_matches": [...],
  "total_matches": 3
}
```

---

## Insurance Claims

### Create a Claim

**POST** `/api/claims/`
*Roles: company_agent (any cow), farmer (own cows only)*

**Request (JSON):**
```json
{
  "cow_profile_id": 1,
  "reason": "dead",
  "notes": "Found dead in the field this morning."
}
```

`reason` values: `dead`, `sick`, `other`.

**Response (201):**
```json
{
  "message": "Claim created successfully.",
  "claim": {
    "id": 1,
    "cow_profile": { ... },
    "status": "pending",
    "reason": "dead",
    "notes": "Found dead in the field this morning.",
    "created_by": { "id": 5, "username": "farmer_john", ... },
    "submitted_at": "2026-03-07T11:00:00Z",
    "assigned_to": null,
    "assigned_at": null,
    "assigned_by": null,
    "verification_result": null,
    "verified_at": null,
    "verified_by": null,
    "verification_notes": "",
    "approved_at": null,
    "approved_by": null,
    "approval_notes": "",
    "updated_at": "2026-03-07T11:00:00Z"
  }
}
```

---

### List Claims

**GET** `/api/claims/`
*Roles: company_agent (all claims), farmer (own claims only)*

**Query parameters:**

| Param | Description |
|-------|-------------|
| `status` | Filter by status: `pending`, `approved`, `rejected` |
| `cow_profile_id` | Filter by cow profile ID |

**Response:**
```json
{
  "count": 3,
  "claims": [ ... ]
}
```

---

### Assign Agent to Verify Claim

**POST** `/api/claims/<id>/assign/`
*Roles: admin only*

Admin assigns a company agent to verify a claim.

**Request (JSON):**
```json
{ "agent_id": 2 }
```

**Response:**
```json
{
  "message": "Claim #1 assigned to agent agent1.",
  "claim": { ... }
}
```

---

### Verify Claim (Agent)

**POST** `/api/claims/<id>/verify/`
*Roles: company_agent only (must be the assigned agent)*

Agent records their verification result (yes/no). Does **not** approve or reject the claim — that is the admin's responsibility.

**Request (JSON):**
```json
{
  "verification_result": true,
  "verification_notes": "Cow confirmed dead on-site."
}
```

`verification_result`: `true` = confirmed / `false` = not confirmed.

**Response:**
```json
{
  "message": "Verification recorded.",
  "claim": { ... }
}
```

**Error (403)** if the agent is not the one assigned:
```json
{ "error": "You are not assigned to verify this claim." }
```

---

### Final Approve / Reject Claim

**POST** `/api/claims/<id>/approve/`
*Roles: admin only*

Admin makes the final decision on a claim.

**Request (JSON):**
```json
{
  "action": "approve",
  "approval_notes": "Verification confirmed. Claim approved."
}
```

`action` values: `approve`, `reject`.

**Response:**
```json
{
  "message": "Claim #1 has been approved.",
  "claim": { ... }
}
```

---

## Admin Endpoints

### Dashboard / Stats

**GET** `/api/admin/dashboard/`
*Roles: admin only*

**Response:**
```json
{
  "total_registered_cows": 50,
  "total_company_agents": 5,
  "total_farmers": 20,
  "claims": {
    "pending": 8,
    "approved": 15,
    "rejected": 3,
    "unassigned_pending": 4,
    "verified_by_agent": 12
  }
}
```

---

### List All Company Agents

**GET** `/api/admin/company-agents/`
*Roles: admin only*

**Response:**
```json
{
  "count": 5,
  "company_agents": [
    {
      "id": 2,
      "username": "agent1",
      "email": "agent1@company.com",
      "first_name": "Ali",
      "last_name": "Hassan",
      "date_joined": "2026-01-01T00:00:00Z",
      "user_type": "company_agent",
      "verified_claims_count": 7
    }
  ]
}
```

---

### List All Farmers

**GET** `/api/admin/farmers/`
*Roles: admin only*

**Response:**
```json
{
  "count": 20,
  "farmers": [
    {
      "id": 5,
      "username": "farmer_john",
      "email": "john@farm.com",
      "first_name": "John",
      "last_name": "Doe",
      "date_joined": "2026-01-15T00:00:00Z",
      "user_type": "farmer",
      "cow_count": 3
    }
  ]
}
```

---

### List All Claims (Admin View)

**GET** `/api/admin/claims/`
*Roles: admin only*

Full claim detail including who verified and who approved each claim.

**Query parameters:**

| Param | Description |
|-------|-------------|
| `status` | Filter: `pending`, `approved`, `rejected` |
| `verified_by` | Filter by verifying agent's user ID |
| `assigned_to` | Filter by assigned agent's user ID |

**Response:**
```json
{
  "count": 26,
  "claims": [
    {
      "id": 1,
      "cow_profile": { "cow_name": "Bella", "policy_id": "POL-...", ... },
      "status": "approved",
      "reason": "dead",
      "notes": "...",
      "created_by": { "id": 5, "username": "farmer_john", ... },
      "submitted_at": "2026-03-07T11:00:00Z",
      "assigned_to": { "id": 2, "username": "agent1", ... },
      "assigned_at": "2026-03-07T12:00:00Z",
      "assigned_by": { "id": 1, "username": "admin_user", ... },
      "verification_result": true,
      "verified_at": "2026-03-07T14:00:00Z",
      "verified_by": { "id": 2, "username": "agent1", ... },
      "verification_notes": "Cow confirmed dead on-site.",
      "approved_at": "2026-03-07T15:00:00Z",
      "approved_by": { "id": 1, "username": "admin_user", ... },
      "approval_notes": "Verification confirmed. Claim approved.",
      "updated_at": "2026-03-07T15:00:00Z"
    }
  ]
}
```

---

## Error Responses

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Validation error — response body contains field-level errors |
| 401 | Missing or invalid JWT token |
| 403 | Authenticated but wrong role for this action |
| 404 | Resource not found |
| 503 | ML model not available (not trained yet) |

---

## Claim Lifecycle

```
Farmer or Agent  →  POST /api/claims/          → status: pending
Admin            →  POST /api/claims/<id>/assign/  → assigned_to = agent
Agent            →  POST /api/claims/<id>/verify/  → verification_result recorded
Admin            →  POST /api/claims/<id>/approve/ → status: approved | rejected
```

---

## Quick-start: Creating Your First Users

Since users can only be created via the API (agents are created by an admin, farmers by agents), you need to bootstrap an admin account using the Django management command:

```bash
cd cow_detection_backend
python manage.py shell -c "
from django.contrib.auth.models import User
from api.models import UserProfile

# Create admin
admin = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass123')
UserProfile.objects.create(user=admin, user_type='admin')

# Create a company agent
agent = User.objects.create_user('agent1', 'agent@company.com', 'agentpass123')
UserProfile.objects.create(user=agent, user_type='company_agent')

print('Done.')
"
```

Then log in via **POST** `/api/login/` and use the returned `access` token for all subsequent requests.
