# PostgreSQL Migration Guide

## Summary of Changes

This document outlines all changes needed to migrate from SQLite to PostgreSQL on Railway.

## 1. Dependencies Added

**requirements.txt:**
- Added `psycopg2-binary==2.9.9`

## 2. Database Connection Updated

**api/main.py:**
- Added conditional database connection based on `DATABASE_URL` environment variable
- PostgreSQL: Uses `psycopg2` with `RealDictCursor` for dict-like row access
- SQLite: Falls back to `sqlite3` for local development
- Both use context manager pattern for proper connection handling

## 3. SQL Syntax Changes Required

### Placeholders
- **SQLite:** `?` placeholders
- **PostgreSQL:** `%s` placeholders
- **Solution:** Use `execute_query()` helper function that handles both

### Primary Keys
- **SQLite:** `INTEGER PRIMARY KEY AUTOINCREMENT`
- **PostgreSQL:** `SERIAL PRIMARY KEY`
- **Status:** ✅ Updated in partner_applications table creation

### Timestamps
- **SQLite:** `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- **PostgreSQL:** `TIMESTAMP DEFAULT NOW()`
- **Status:** ✅ Updated in table creation statements

### Data Types
- **SQLite:** `TEXT` (works fine)
- **PostgreSQL:** `VARCHAR` or `TEXT` (both work, using `VARCHAR` for shorter fields)
- **Status:** ✅ Updated in table creation statements

### Returning IDs
- **SQLite:** `cursor.lastrowid`
- **PostgreSQL:** `RETURNING id` clause + `cursor.fetchone()['id']`
- **Status:** ✅ Updated in partner application insertion

## 4. Queries That Need Updating

### Already Updated:
- ✅ `partner_applications` table creation
- ✅ `partner_applications` INSERT query
- ✅ `get_partner_applications_api()` endpoint
- ✅ `init_db()` table creation for failed_emails, password_reset_tokens, error_logs

### Still Need Updating:
- ⚠️ All queries using `db.execute()` directly (need to use `execute_query()` helper)
- ⚠️ Queries in `/api/login` endpoint
- ⚠️ Queries in `/api/verify-session` endpoint
- ⚠️ Queries in `/api/change-password` endpoint
- ⚠️ Queries in `/api/logout` endpoint
- ⚠️ Queries in email gate tracking endpoints
- ⚠️ Queries in Stripe webhook handler
- ⚠️ Queries in admin endpoints
- ⚠️ Queries in broker referral endpoints

## 5. Testing Checklist

After deployment:
1. ✅ Verify `DATABASE_URL` is set in Railway environment variables
2. ✅ Test partner application form submission
3. ✅ Test admin dashboard partner applications loading
4. ✅ Test user login/authentication
5. ✅ Test email gate tracking
6. ✅ Test Stripe webhook processing
7. ✅ Test broker referral tracking

## 6. Migration Steps

1. Add PostgreSQL service to Railway project
2. Set `DATABASE_URL` environment variable in Railway
3. Deploy updated code
4. Run `init_db()` to create tables (or use schema.sql)
5. Test all endpoints
6. Monitor logs for any SQL syntax errors

## Notes

- The code now supports both PostgreSQL (production) and SQLite (local dev)
- When `DATABASE_URL` is set, PostgreSQL is used
- When `DATABASE_URL` is not set, SQLite is used (local development)
- All table creation statements check `DB_TYPE` and use appropriate syntax

