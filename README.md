# Job Board Platform

A backend API for a job board that connects employers and candidates: employers post and manage job listings and review applicants, candidates search for jobs and apply with a resume, and administrators oversee the platform through Django Admin.

This is a backend/API project. It is meant to be used through API calls (curl, Postman, or any HTTP client) and through Django Admin — there is no bundled frontend.

## Overview

The platform models three kinds of users — candidates, employers, and administrators — and enforces what each of them can do entirely on the server. Employers manage a company profile and job listings; candidates manage a profile and a resume and apply to jobs; every privileged action (editing a job, changing an application's status, downloading a resume) is checked against the authenticated user, never against values the client sends.

## Features

- Token-based authentication (signup, login, logout)
- Role-based accounts: `CANDIDATE`, `EMPLOYER`, `ADMIN` — roles cannot be self-escalated through the signup API
- Employer company profiles
- Candidate profiles with skills, experience, and education
- Resume upload with extension, size, and content-type validation, safe (non-guessable) storage filenames, and access control
- Job listings with full validation (salary ranges, controlled choice fields, deadlines)
- Public job search, filtering, ordering, and pagination
- Job applications with a full status lifecycle, duplicate-application prevention, and candidate withdrawal
- In-app notifications for employers (new applications) and candidates (status changes)
- A Django Admin configuration covering every model, with useful list displays, filters, and search
- An automated test suite covering authentication, ownership, validation, the application lifecycle, and authorization/IDOR cases

## Technology Stack

- Python 3.12
- Django 5.0
- Django REST Framework 3.15
- django-filter 25.1
- SQLite (local development database)
- DRF Token Authentication
- `python-dotenv` for environment configuration
- Django's built-in test runner / DRF `APITestCase`

No Docker, Celery, Redis, PostgreSQL, or other infrastructure is used — none of it was needed for a project of this size, and adding it would only make the project harder to run locally.

## Architecture

```
job-board/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── config/                # Project settings, root URLs, WSGI/ASGI, error envelope
│
├── accounts/               # Custom User model + roles, signup/login/logout, shared permission classes
│   ├── models.py            # User (role: CANDIDATE / EMPLOYER / ADMIN)
│   ├── serializers.py
│   ├── views.py
│   ├── permissions.py       # IsCandidate / IsEmployer / IsAdminRole
│   └── tests.py
│
├── employers/               # Company profiles
│   ├── models.py             # EmployerProfile (one-to-one with User)
│   ├── serializers.py
│   ├── views.py              # GET/PATCH /api/employers/me/
│   └── tests.py
│
├── candidates/               # Candidate profiles + resumes
│   ├── models.py               # CandidateProfile, Resume
│   ├── validators.py           # Resume file validation (extension, size, content-type, magic bytes)
│   ├── services.py             # Safe resume replace/delete logic
│   ├── views.py                # profile + resume upload/download/delete
│   └── tests.py
│
└── jobs/                       # Jobs, applications, notifications
    ├── models.py                 # Job, Application, Notification + controlled choices
    ├── services.py                # create_application / update_application_status / withdraw_application
    ├── filters.py                  # Whitelisted job search/filter fields
    ├── permissions.py
    ├── views.py
    └── tests.py
```

Each app owns one clear responsibility. Business rules that touch more than one write (for example, creating an application *and* a notification) live in a `services.py` module and run inside `transaction.atomic()`.

## User Roles

- **Candidate** — manages their own profile and resume, searches/browses jobs, applies to jobs, views and withdraws their own applications.
- **Employer** — manages their own company profile, creates and edits their own job listings, closes their own listings, views and updates the status of applications submitted to their own jobs.
- **Admin / staff** — manages the platform through Django Admin (users, employers, candidates, jobs, applications, resumes, notifications).

A user's role is set at signup and cannot be changed by the client afterward through the API. `ADMIN` is never an option at signup — it is only ever granted through `createsuperuser` or Django Admin.

## Installation

```bash
# 1. Clone the repository
git clone <your-repository-url> job-board
cd job-board

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # macOS/Linux
# .venv\Scripts\Activate.ps1         # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your local environment file
cp .env.example .env                 # macOS/Linux
# Copy-Item .env.example .env        # Windows PowerShell

# 5. Run migrations
python manage.py migrate

# 6. Create an administrator account
python manage.py createsuperuser

# 7. Run the test suite
python manage.py test

# 8. Start the development server
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000/api/...` and Django Admin at `http://127.0.0.1:8000/admin/`.

## Environment Variables

Configuration is read from a `.env` file (see `.env.example`); never commit a real `.env` file.

| Variable | Purpose | Example |
|---|---|---|
| `SECRET_KEY` | Django's cryptographic signing key | a long random string |
| `DEBUG` | Enables Django's debug mode | `True` for local development, `False` otherwise |
| `ALLOWED_HOSTS` | Comma-separated hostnames the app will serve | `localhost,127.0.0.1` |
| `RESUME_MAX_UPLOAD_MB` | Maximum resume upload size, in megabytes | `5` |

## API Documentation

All endpoints are under `/api/`. Every error response uses the same envelope:

```json
{ "success": false, "error": "Human readable message", "code": "SOME_ERROR_CODE" }
```

### Authentication (`/api/auth/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/signup/` | Public | Create a `CANDIDATE` or `EMPLOYER` account |
| POST | `/api/auth/login/` | Public | Exchange credentials for a token |
| POST | `/api/auth/logout/` | Token | Invalidate the current token |
| GET | `/api/auth/me/` | Token | Current authenticated user |

Signup example:

```json
POST /api/auth/signup/
{ "username": "jane", "email": "jane@example.com", "password": "SecurePassword123", "role": "CANDIDATE" }
```

Every authenticated request sends `Authorization: Token <token>`.

### Employers (`/api/employers/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/employers/me/` | Employer | View own company profile (created automatically on first access) |
| PATCH | `/api/employers/me/` | Employer | Update own company profile |

### Candidates (`/api/candidates/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/candidates/me/` | Candidate | View own profile |
| PATCH | `/api/candidates/me/` | Candidate | Update own profile |
| GET | `/api/candidates/me/resume/` | Candidate | Own resume metadata |
| POST | `/api/candidates/me/resume/` | Candidate | Upload/replace own resume (`multipart/form-data`, field `file`) |
| DELETE | `/api/candidates/me/resume/` | Candidate | Delete own resume |
| GET | `/api/candidates/me/resume/download/` | Candidate | Download own resume file |

(The same resume operations are also reachable at `/api/resumes/` and `/api/resumes/download/`.)

### Jobs (`/api/jobs/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/jobs/` | Public | List open jobs (search/filter/order/paginate) |
| POST | `/api/jobs/` | Employer | Create a job (ownership derived from the token, never from the request body) |
| GET | `/api/jobs/<id>/` | Public | Job detail (reachable even if closed, so its real status is visible) |
| PATCH | `/api/jobs/<id>/` | Owning employer | Update a job |
| DELETE | `/api/jobs/<id>/` | Owning employer | Delete a job |
| POST | `/api/jobs/<id>/close/` | Owning employer | Close a job (`status` → `CLOSED`) |

Query parameters on `GET /api/jobs/`:

- `search=python` — matches title, description, location, and company name
- `location=`, `employment_type=`, `experience_level=`, `status=`, `salary_min=`, `salary_max=`
- `ordering=created_at` / `-created_at` / `application_deadline` / `salary_min` / `salary_max` / `title` (any other value is ignored, never passed through to raw SQL)
- Standard DRF page-number pagination (`?page=2`), 10 results per page by default

Job creation example:

```json
POST /api/jobs/
{
  "title": "Backend Developer",
  "description": "We are looking for a Python developer...",
  "location": "Lahore",
  "employment_type": "FULL_TIME",
  "experience_level": "ENTRY",
  "salary_min": 80000,
  "salary_max": 120000,
  "currency": "PKR",
  "skills": ["Python", "Django", "REST API"],
  "application_deadline": "2026-12-31"
}
```

### Applications (`/api/applications/`, `/api/employer/applications/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/applications/` | Candidate | List own applications |
| POST | `/api/applications/` | Candidate | Apply to a job |
| GET | `/api/applications/<id>/` | Owning candidate or owning employer | Application detail |
| PATCH | `/api/applications/<id>/status/` | Owning employer | Change application status |
| POST | `/api/applications/<id>/withdraw/` | Owning candidate | Withdraw an application |
| GET | `/api/applications/<id>/resume/` | Owning candidate or owning employer | Download the resume attached to that application |
| GET | `/api/employer/applications/` | Employer | List applications submitted to the employer's own jobs (filter with `?status=` / `?job=`) |

Apply example:

```json
POST /api/applications/
{ "job_id": 12, "resume_id": 5, "cover_letter": "I am interested in this position..." }
```

The server identifies the applicant from the token, verifies the job exists and is open, checks the deadline, confirms the resume (if any) belongs to the candidate, and blocks duplicate active applications — none of this is trusted from the request body.

### Notifications (`/api/notifications/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/notifications/` | Any authenticated user | Own notifications (filter with `?is_read=false`) |
| PATCH | `/api/notifications/<id>/read/` | Owning recipient | Mark a notification as read |

Notifications are database-backed and in-app only. No email, SMS, or real-time (WebSocket) delivery is implemented — if you need those, they are a deliberate future extension, not something this project claims to already do.

## Resume Upload

- **Allowed file types:** `.pdf`, `.doc`, `.docx` (extension and content-type are both checked; PDF uploads are additionally checked for the `%PDF-` header, since extension and content-type can both be spoofed by a client)
- **Maximum size:** 5 MB by default, configurable via `RESUME_MAX_UPLOAD_MB`
- **Storage:** each file is renamed to a random UUID-based name on disk under `media/resumes/<user id>/`; the original filename is preserved only as metadata, so a malicious filename can never influence the storage path
- **Replacement:** a candidate has at most one resume record. Uploading again replaces the file and record in place (`candidates.services.replace_resume`) rather than accumulating duplicates, and the old file is deleted from disk once the new one is safely stored
- **Privacy:** resume files are never served through a public `/media/...` URL. They can only be retrieved through authenticated endpoints: the candidate's own `/api/candidates/me/resume/download/`, or `/api/applications/<id>/resume/`, which an employer can only use for an application submitted to one of *their own* jobs

## Application Lifecycle

```
APPLIED → UNDER_REVIEW → SHORTLISTED → INTERVIEW → HIRED
                     ↘ REJECTED (from APPLIED, UNDER_REVIEW, SHORTLISTED, or INTERVIEW)
```

A candidate may withdraw an active application (`WITHDRAWN`) at any point before it reaches `HIRED`. `WITHDRAWN` and `REJECTED` applications are not counted against the one-active-application-per-job rule, so a candidate can apply again after withdrawing.

Status changes are one-directional and validated server-side (`jobs.models.EMPLOYER_ALLOWED_TRANSITIONS`): an employer can only make a listed transition on a job they own, and a candidate can never set an employer-controlled status (such as `HIRED`) directly — the status-update endpoint is employer-only.

## Permissions

- **Public:** browse and search jobs, view job detail
- **Candidate:** manage own profile and resume, apply to jobs, view/withdraw own applications, view own notifications
- **Employer:** manage own company profile, create/edit/close own jobs, view and update applications submitted to own jobs, view own notifications
- **Admin/staff:** full access through Django Admin

Every one of these rules is enforced in `permission_classes` and object-level permission checks (`has_object_permission`) — never by hiding a button on a client that doesn't exist in this project.

## Testing

```bash
python manage.py test            # run everything
python manage.py test jobs       # run one app's tests
python manage.py test -v 2       # verbose output
```

The suite (105 tests, all passing at time of writing) covers:

- Signup/login/logout, duplicate username/email, weak passwords, role-escalation attempts
- Employer and candidate profile ownership (a user can never edit another user's profile)
- Job creation, validation (salary ranges, deadlines, employment type, blank fields), ownership enforcement on edit/close/delete
- Public job listing: search, filtering, combined filters, ordering (including that an unapproved ordering field is safely ignored, not passed to raw SQL), pagination
- Resume upload: valid PDF/DOCX, rejected extension, oversized file, spoofed PDF magic bytes, replacement instead of duplication, download authorization
- Applications: creation, duplicate prevention, resume-ownership checks, closed/expired job rejection, candidate-only application lists that can't be bypassed with a query parameter
- Employer-side application list scoped strictly to the employer's own jobs
- Status transitions: valid and invalid transitions, candidates blocked from the employer-only status endpoint, withdrawal rules
- Notifications: created on application submission, scoped to the correct recipient, read/unread filtering, ownership on mark-as-read
- IDOR checks across applications, resumes, and jobs with two independent employers and two independent candidates

As part of building this project, the job-ownership permission check was deliberately broken, the test suite was re-run to confirm `test_other_employer_cannot_edit_job` and `test_other_employer_cannot_delete_job` failed as expected, and the correct implementation was then restored and the full suite re-verified to pass.

## Known Limitations

- SQLite is used for local development, as specified. A real deployment would normally use a production-grade database (e.g. PostgreSQL) and a proper `DATABASES` configuration for that environment — this project does not attempt to configure or claim production deployment.
- Notifications are in-app/database-backed only; there is no email or push delivery.
- There is no automated CI pipeline configured in this repository.
- Resume "virus scanning" is out of scope; validation covers extension, size, and content-type/magic-byte checks, not malware scanning.
- The admin-role signal that upgrades a superuser's `role` field is not automatic — `createsuperuser` sets `is_staff`/`is_superuser`, which already grants full admin access, but the `role` field on that account defaults to `CANDIDATE` unless changed manually in Django Admin. This does not affect authorization (`is_admin_role` checks `is_staff`/`is_superuser` as well as `role`), but it is worth knowing about if you inspect the `role` column directly.
