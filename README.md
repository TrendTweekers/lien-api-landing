# LienDeadline API & Dashboard

## Source of Truth

### Backend
- **FastAPI application:** `/api`
- **Main entry point:** `api/main.py`
- **Deployment:** Railway uses `Procfile` and `nixpacks.toml` → `uvicorn api.main:app`

### Customer Dashboard
- **Build output (served in production):** `/public/dashboard`
- **Source code:** `/dashboard` (React + Vite)
- **Served at:** `/dashboard/*` via FastAPI SPA routing

### Broker Dashboard
- **Tolt dashboard:** Configured via `TOLT_DASHBOARD_URL` env var (defaults to `/partners.html`)

## Archived Duplicates

- **`/_archive`** - Contains archived duplicate code that is NOT used in production
  - Do NOT edit files in `_archive/`
  - Do NOT restore duplicates to root directory
  - See `_archive/README.md` for details

## Development

See `DEV_NOTES.md` and `UI_WORKFLOW.md` for development workflows.

