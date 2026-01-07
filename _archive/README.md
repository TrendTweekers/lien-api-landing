# Archive Directory

## Purpose

This directory contains archived/duplicate copies of code that are **NOT used in production**.

## ⚠️ Important: Do NOT Edit Archived Files

**Production uses files from the root directory, NOT from `_archive/`.**

### How Production Works

Railway deployment uses:
- **Procfile:** `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **nixpacks.toml:** `cmd = "python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT"`

Both reference `api.main:app` from the **root directory**, not from any nested/archived copies.

### Archived Items

- `lien-api-landing_DUPLICATE_DO_NOT_USE/` - Nested duplicate repository copy (not used by Railway)

## Why Archived?

These directories were identified as duplicates that:
1. Are not referenced by Railway deployment configuration
2. Contain outdated code (e.g., old QuickBooks integration)
3. Could cause confusion if edited instead of root files
4. Are kept for reference/history but should not be modified

## Editing Code

**Always edit files in the root directory:**
- ✅ `api/main.py` (root)
- ❌ `_archive/lien-api-landing_DUPLICATE_DO_NOT_USE/api/main.py` (archived, do not edit)

