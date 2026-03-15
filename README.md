# PCM System

Production-ready, multi-tenant PCM record-keeping and reporting system for campus ministries.

## Stack
- FastAPI + SQLAlchemy + Alembic
- PostgreSQL
- React (Vite + TS) + React Router + React Query + Tailwind
- JWT access + refresh tokens
- Pandas + OpenPyXL for report parsing

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
make up
```

Services:
- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173

Default admin (from `.env`):
- email: `admin@pcm.local`
- password: `admin123`

## Migrations

```bash
cd backend
alembic upgrade head
```

## Features
- Multi-tenant access by university
- RBAC: admin, university_admin, leader, data_clerk, viewer
- Membership records + alumni transition job
- Report templates (versioned), upload + parsing
- Analytics endpoints for membership and reports
- Audit log viewer

## Reporting workflow
1) Create templates in the UI (comma-separated columns)
2) Download template CSV
3) Upload CSV or Excel report
4) Parsed rows stored in DB

## CSV bulk upload for members
Columns: `member_id,first_name,last_name,gender,phone,email,university_id,program_id,start_year,expected_graduation_date,intake,status,active`

## Scripts
- `make up` / `make down`
- `make migrate`
- `make backend` / `make frontend`

## CI/CD
- GitHub Actions CI is in `.github/workflows/ci.yml`
- AWS deployment workflow is in `.github/workflows/deploy-aws.yml` and follows the low-cost Lightsail + S3 path
- Managed AWS setup notes are in `deplody/aws/README.md`
- Lowest-cost AWS setup notes are in `deploy/aws/README-low-cost.md`

## Notes
- File uploads stored in `/data/uploads` (Docker volume `pcm_uploads`).
- Only Admin can access audit logs and user management.
