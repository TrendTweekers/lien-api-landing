# Database Migration Guide

## Emergency Database Fix

This guide explains how to run the emergency database migration to fix production issues.

## Prerequisites

1. Railway CLI installed: `npm i -g @railway/cli`
2. Logged into Railway: `railway login`
3. Connected to your project: `railway link`

## Step 1: Run the Migration

After Railway redeploys (automatic after git push), run:

```bash
railway run python api/migrations/fix_production_database.py
```

**Expected Output:**
```
============================================================
🔧 EMERGENCY DATABASE FIX
============================================================
Database Type: postgresql

1️⃣ Checking customers table...
   ✅ Customers table created

2️⃣ Checking api_keys table...
   ✅ API keys table created

3️⃣ Checking lien_deadlines table...
   📊 Current states in database: 5

4️⃣ Repopulating all 51 states...
   🗑️ Cleared existing states
   ✅ Inserted 51 states
   📊 Final state count: 51
   ✅ Hawaii verified: Hawaii - 45 days

============================================================
🎉 DATABASE FIX COMPLETE!
============================================================
```

## Step 2: Verify the Fix

Run the verification script:

```bash
railway run python api/migrations/verify_database.py
```

**Expected Output:**
```
============================================================
🔍 DATABASE VERIFICATION
============================================================
Database Type: postgresql

1️⃣ Checking customers table...
   ✅ Customers table exists (0 records)

2️⃣ Checking api_keys table...
   ✅ API keys table exists (0 records)

3️⃣ Checking lien_deadlines table...
   ✅ Total states: 51
   ✅ Hawaii verified:
      State: Hawaii
      Lien deadline: 45 days
      Prelim required: False

   📊 Sample states:
      AK: Alaska - 120 days
      CA: California - 90 days
      NY: New York - 240 days
      TX: Texas - None days

============================================================
✅ VERIFICATION COMPLETE
============================================================
```

## Step 3: Quick Verification Commands

### A) Count states:
```bash
railway run python -c "from api.database import get_db, get_db_cursor, DB_TYPE; conn = next(get_db()); cursor = get_db_cursor(conn); cursor.execute('SELECT COUNT(*) FROM lien_deadlines'); result = cursor.fetchone(); print(f'Total states: {result[0] if DB_TYPE == \"postgresql\" else result[0]}')"
```

Expected: `Total states: 51`

### B) Test Hawaii specifically:
```bash
railway run python -c "from api.database import get_db, get_db_cursor, DB_TYPE; conn = next(get_db()); cursor = get_db_cursor(conn); cursor.execute(\"SELECT state_name, lien_filing_days FROM lien_deadlines WHERE state_code = 'HI'\"); row = cursor.fetchone(); print(f'Hawaii: {row[\"state_name\"] if DB_TYPE == \"postgresql\" else row[0]}, Lien deadline: {row[\"lien_filing_days\"] if DB_TYPE == \"postgresql\" else row[1]} days')"
```

Expected: `Hawaii: Hawaii, Lien deadline: 45 days`

## Step 4: Test API Endpoint

Test the calculator API:

```bash
curl -X POST https://liendeadline.com/api/v1/calculate-deadline \
  -H "Content-Type: application/json" \
  -d '{"invoice_date": "2026-01-24", "state": "HI"}'
```

**Expected Response:**
```json
{
  "state": "Hawaii",
  "state_code": "HI",
  "invoice_date": "2026-01-24",
  "preliminary_notice": {
    "required": false,
    "deadline": null,
    "days_from_now": null,
    "urgency": null,
    "description": ""
  },
  "lien_filing": {
    "deadline": "2026-03-10",
    "days_from_now": 45,
    "urgency": "warning",
    "description": "45 days after the date of completion of the improvement"
  },
  "warnings": ["⚠️ SHORTEST DEADLINE IN US - Only 45 days! Notice of Completion can trigger this deadline."],
  "statute_citations": ["Haw. Rev. Stat. §507-43"],
  "notes": "SHORTEST DEADLINE IN US - Only 45 days! Notice of Completion can trigger this deadline.",
  "quota": {
    "unlimited": false,
    "remaining": 2,
    "limit": 3
  }
}
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'api'"

**Solution:** Make sure you're running from the project root or Railway's working directory includes the project root.

### Issue: "Table already exists"

**Solution:** This is normal. The script checks if tables exist before creating them. It's safe to run multiple times.

### Issue: "Only 5 states found"

**Solution:** The migration script should populate all 51 states. If it doesn't, check:
1. The `add_all_states.py` file has all 51 states in STATE_DATA
2. No errors occurred during insertion (check Railway logs)
3. Run the migration script again

### Issue: "Hawaii not found"

**Solution:** 
1. Check if the state was inserted: `railway run python -c "from api.database import get_db, get_db_cursor, DB_TYPE; conn = next(get_db()); cursor = get_db_cursor(conn); cursor.execute('SELECT * FROM lien_deadlines WHERE state_code = \\'HI\\''); print(cursor.fetchone())"`
2. If empty, re-run the migration script

## Files

- `fix_production_database.py` - Main migration script
- `verify_database.py` - Verification script
- `add_all_states.py` - Contains STATE_DATA with all 51 states

## Support

If issues persist:
1. Check Railway logs: `railway logs`
2. Verify database connection: `railway variables` (check DATABASE_URL)
3. Test locally first: `python api/migrations/fix_production_database.py` (requires local DB setup)

