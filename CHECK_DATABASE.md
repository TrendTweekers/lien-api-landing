# Database State Check Instructions

## Quick Check (Local Development)

Run this command from project root:
```bash
python api/migrations/check_database_states.py
```

## Railway Production Check

### Option 1: Using Railway CLI

```bash
# Connect to Railway PostgreSQL database
railway run psql $DATABASE_URL

# Then run this query:
SELECT state_code, state_name FROM lien_deadlines ORDER BY state_code;

# Count states:
SELECT COUNT(*) FROM lien_deadlines;

# Expected: 51 states (50 US states + DC)
```

### Option 2: Using Railway Run Script

```bash
# Run the check script on Railway
railway run python api/migrations/check_database_states.py
```

## If States Are Missing

Run the migration to populate all 51 states:

```bash
railway run python api/migrations/fix_production_database.py
```

This script will:
1. Check current state count
2. If < 51, clear and repopulate all states
3. Verify all 51 states are present

## Expected States (51 total)

AL, AK, AZ, AR, CA, CO, CT, DE, DC, FL, GA, HI, IA, ID, IL, IN, KS, KY, LA, ME, MD, MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC, SD, TN, TX, UT, VT, VA, WA, WV, WI, WY

