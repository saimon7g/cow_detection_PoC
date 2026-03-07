# Cow Insurance Management System

A system for registering cattle, managing farmer profiles, and processing livestock insurance claims — backed by AI-powered cow identification using muzzle photos.

---

## User Roles

The system has three types of users. Each has a distinct set of responsibilities.

| Role | Description |
|------|-------------|
| **Admin** | Oversees the entire system. Assigns agents, makes final decisions on claims, and monitors all activity. |
| **Company Agent** | Field staff who register cows, create farmer accounts, and verify claims on the ground. |
| **Farmer** | Livestock owners who view their registered cows and submit insurance claims. |

---

## Admin

The admin has full visibility across the system and makes the final call on every insurance claim.

### What an admin can do

**Monitor the system**
- View a dashboard showing total registered cows, total farmers, total agents, and a breakdown of claim statuses (pending / approved / rejected).

**Manage people**
- View all company agent profiles, including how many claims each agent has verified.
- View all farmer profiles, including how many cows are registered under each farmer.

**Handle insurance claims**
- View all claims with complete detail: who submitted the claim, which agent was assigned to verify it, what the agent's verification result was, and the final decision.
- Filter claims by status, by assigned agent, or by verifying agent.
- **Assign** a company agent to verify a specific claim.
- **Approve or reject** a claim after reviewing the agent's verification result (final decision).

> The admin is the only person who can give final approval or rejection on an insurance claim.

---

## Company Agent

Company agents are the primary field operators. They create farmer accounts, register cows, and carry out on-site claim verifications.

### What a company agent can do

**Manage farmers**
- Create a new farmer account (username, password, contact details).
- View the list of all farmers with their cow counts.

**Register cows**
- Register a new cow under a specific farmer's profile.
- Upload cow photos and muzzle photos during registration (muzzle photos are used by the AI model to identify the cow).
- A unique policy ID and cow ID are automatically generated for every registration.

**Create insurance claims**
- Open a claim on behalf of any cow in the system (e.g. if a farmer reports a cow as dead or sick).

**Verify claims (when assigned by admin)**
- An agent can only verify a claim if the admin has specifically assigned that claim to them.
- The agent visits the farm, confirms the situation, and records a **yes/no** verification result along with notes.
- The agent **does not approve or reject** the claim — that decision belongs to the admin.

**Identify cows**
- Use the AI classification tool to identify a cow from a photo by matching it against registered muzzle prints.

---

## Farmer

Farmers are the registered livestock owners. They can see their own cows and submit insurance claims when needed.

### What a farmer can do

**View my cows**
- See the full list of cows registered under their profile, including each cow's name, breed, age, policy ID, and registration date.
- Farmers only see their own cows — they cannot see cows belonging to other farmers.

**Submit an insurance claim**
- Open a claim for one of their own cows if it is dead, sick, or otherwise in need of insurance coverage.
- Provide the reason (dead, sick, or other) and any additional notes.
- Track the status of their submitted claims (pending → verified by agent → approved/rejected by admin).

> A farmer cannot register a cow themselves — that must be done by a company agent.

---

## How a Claim Works (End to End)

```
1. Farmer or Agent   →  Submits a claim for a cow
2. Admin             →  Reviews the claim and assigns an agent to verify it
3. Agent             →  Visits the farm and records verification (yes/no)
4. Admin             →  Reviews the verification and gives final approval or rejection
```

---

## Getting Started

- **For setup and installation**, see [SETUP.md](SETUP.md).
- **For API endpoint reference**, see [API_DOCUMENTATION.md](cow_detection_backend/API_DOCUMENTATION.md).

---

## Technology

- **Backend**: Django + Django REST Framework
- **Authentication**: JWT (JSON Web Token)
- **Cow Identification**: Contrastive autoencoder trained on muzzle photos
- **Database**: SQLite (development)
