# Users Table Migration Fix - Verification Guide

## Overview
This document provides curl commands to verify that the users table migration endpoint works correctly.

## Prerequisites
- Admin credentials: `admin:LienAPI2025` (or your configured `ADMIN_USER`/`ADMIN_PASS`)
- Production URL: `https://liendeadline.com`

## Verification Steps

### 1. Run Migration Endpoint

**First run (should create table):**
```bash
curl -X GET "https://liendeadline.com/api/admin/migrate-users-table" \
  -u admin:LienAPI2025 \
  -H "Accept: application/json"
```

**Expected Response (200 OK):**
```json
{
  "status": "ok",
  "created": true,
  "message": "Users table migration completed successfully"
}
```

**Second run (should detect existing table):**
```bash
curl -X GET "https://liendeadline.com/api/admin/migrate-users-table" \
  -u admin:LienAPI2025 \
  -H "Accept: application/json"
```

**Expected Response (200 OK):**
```json
{
  "status": "ok",
  "created": false,
  "message": "Users table already exists"
}
```

### 2. Create Test User

**After migration succeeds, create a test user:**
```bash
curl -X POST "https://liendeadline.com/api/admin/create-test-user?email=test@example.com&password=TestPassword123!" \
  -u admin:LienAPI2025 \
  -H "Accept: application/json"
```

**Expected Response (200 OK):**
```json
{
  "status": "success",
  "message": "Test user account created successfully",
  "email": "test@example.com",
  "password": "TestPassword123!",
  "user_id": 1,
  "subscription_status": "active",
  "login_url": "/dashboard",
  "note": "You can now log in at /dashboard with these credentials"
}
```

### 3. Verify Error Handling

**Test with invalid credentials (should return 401):**
```bash
curl -X GET "https://liendeadline.com/api/admin/migrate-users-table" \
  -u wrong:credentials \
  -H "Accept: application/json"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Unauthorized"
}
```

## Error Messages

If migration fails, the endpoint will return detailed error information:

**Example Error Response (500):**
```json
{
  "detail": "Migration failed: Exception('Failed to create users table: ...') (SQLSTATE: 42P07)"
}
```

The error message includes:
- Full exception representation (`repr(e)`)
- SQLSTATE code (if available, for PostgreSQL errors)
- Detailed error message

## Database Schema

The migration creates a `users` table with the following structure:

**PostgreSQL:**
- `id` SERIAL PRIMARY KEY
- `email` VARCHAR UNIQUE NOT NULL
- `password_hash` VARCHAR NOT NULL
- `stripe_customer_id` VARCHAR (nullable)
- `subscription_status` VARCHAR NOT NULL DEFAULT 'inactive'
- `subscription_id` VARCHAR (nullable)
- `session_token` VARCHAR (nullable)
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- `last_login_at` TIMESTAMPTZ (nullable)

**Indexes:**
- Unique index on `email`
- Index on `subscription_status`

## Notes

- The migration is **idempotent** - safe to run multiple times
- Uses `CREATE TABLE IF NOT EXISTS` for PostgreSQL (9.5+)
- Automatically creates indexes if they don't exist
- The `create-test-user` endpoint automatically ensures the table exists before use
- Startup check runs automatically but won't fail startup if migration fails

