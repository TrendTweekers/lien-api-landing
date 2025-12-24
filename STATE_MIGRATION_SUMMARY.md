# State Migration Summary

## ✅ Completed Tasks

### 1. Database Schema Created
- **File**: `database/migrations/005_create_lien_deadlines_table.sql`
- **Table**: `lien_deadlines`
- **Columns**: All required fields including state_code, state_name, preliminary notice fields, lien filing fields, and special rules flags
- **Indexes**: Created on `state_code` for fast lookups

### 2. Migration Script Created
- **File**: `api/migrations/add_all_states.py`
- **Functionality**: 
  - Creates table if it doesn't exist
  - Inserts all 51 states (50 US states + DC)
  - Updates existing states with corrected data
  - Handles both PostgreSQL and SQLite
- **To Run**: `python api/migrations/add_all_states.py`

### 3. API Validation Updated
- **File**: `api/main.py`
- **Changes**:
  - Added `VALID_STATES` constant with all 51 state codes
  - Updated state validation to check against `VALID_STATES` instead of just `STATE_RULES`
  - Added database query fallback in `calculate_deadline` endpoint
  - Updated `/v1/states` endpoint to return all 51 states
  - Added automatic table creation in `init_db()`

### 4. Frontend State Selectors Updated
- **Files**: 
  - `index.html` - Updated main calculator dropdown
  - `customer-dashboard.html` - Updated dashboard calculator dropdown
- **Changes**: Added all 51 states in alphabetical order

## 📊 State Count

**Total States**: 51 (50 US states + DC)

### States Added (22 new states + DC):
- AK (Alaska)
- AR (Arkansas) 
- CT (Connecticut)
- DE (Delaware)
- DC (District of Columbia)
- HI (Hawaii)
- IA (Iowa)
- ID (Idaho)
- KS (Kansas)
- LA (Louisiana)
- ME (Maine)
- MS (Mississippi)
- MT (Montana)
- ND (North Dakota)
- NE (Nebraska)
- NH (New Hampshire)
- NM (New Mexico)
- OK (Oklahoma)
- RI (Rhode Island)
- SD (South Dakota)
- VT (Vermont)
- WV (West Virginia)
- WY (Wyoming)

### States Updated with Corrected Data:
- **TX (Texas)**: Now uses month + day formula instead of flat days
- **AR (Arkansas)**: Now has 75-day preliminary notice (was incorrectly marked as "no notice")
- **AK (Alaska)**: Now has preliminary notice requirement (was incorrectly marked as "no notice")
- **WA (Washington)**: Clarified supplier-specific 60-day preliminary notice
- **OH (Ohio)**: Clarified conditional preliminary notice (only if Notice of Commencement filed)
- **HI (Hawaii)**: Marked as SHORTEST deadline in US (45 days)

## 🔧 Critical State Fixes

1. **Texas (TX)**: Uses month + day formula, NOT flat days
   - Preliminary: 3rd month + 15 days (non-res); 2nd month + 15 days (res)
   - Lien Filing: 4th month + 15 days (non-res); 3rd month + 15 days (res)

2. **Washington (WA)**: Supplier-specific preliminary notice
   - 60-day preliminary notice required for SUPPLIERS
   - Not required for contractors

3. **Ohio (OH)**: Conditional preliminary notice
   - Only required if Notice of Commencement filed
   - 21 days from first furnishing

4. **Hawaii (HI)**: SHORTEST deadline in US
   - Only 45 days for lien filing
   - Needs warning in UI

5. **Louisiana (LA)**: Uses "privilege" not "lien"
   - Different terminology (civil law state)
   - 75-day preliminary notice

6. **Oregon (OR)**: 8 BUSINESS DAYS for preliminary
   - Not calendar days - excludes weekends/holidays

## 📝 Next Steps

1. **Run Migration**:
   ```bash
   python api/migrations/add_all_states.py
   ```

2. **Verify Database**:
   ```sql
   SELECT state_code, state_name, preliminary_notice_required, lien_filing_days 
   FROM lien_deadlines 
   ORDER BY state_code;
   ```
   Expected: 51 rows

3. **Test API**:
   - Test `/v1/states` endpoint returns all 51 states
   - Test calculation endpoint with new states
   - Verify database fallback works

4. **Update Documentation**:
   - Update API docs to list all 51 supported states
   - Update landing page to show "All 50 US States + DC"

## ⚠️ Important Notes

- The API now queries the database first, then falls back to JSON if database query fails
- Table is automatically created on startup if it doesn't exist
- Migration script is idempotent (can be run multiple times safely)
- All state data is from Levelset's verified state guides

