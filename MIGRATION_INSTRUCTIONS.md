# Migration Instructions: Generate Short Codes for Existing Brokers

## Option A: Python Script (Recommended)

This uses our `ShortLinkGenerator` class to ensure proper formatting and uniqueness.

### Steps:

1. **Run the migration script:**
   ```bash
   cd api
   python migrate_existing_brokers.py
   ```

   Or if running from Railway:
   ```bash
   railway run python api/migrate_existing_brokers.py
   ```

2. **The script will:**
   - Find all brokers without short codes
   - Generate unique short codes using email hash
   - Update referral_link to `/r/{short_code}` format
   - Handle collisions automatically
   - Show progress for each broker

---

## Option B: SQL Command (Quick but Less Control)

If you prefer SQL directly, use Railway CLI:

### Steps:

1. **Install Railway CLI (if not already installed):**
   ```powershell
   npm install -g @railway/cli
   ```

2. **Login and link project:**
   ```powershell
   railway login
   cd lien-api-landing
   railway link
   ```

3. **Connect to PostgreSQL:**
   ```powershell
   railway run psql $DATABASE_URL
   ```

4. **Run SQL commands:**

   **For PostgreSQL:**
   ```sql
   -- Add column if not exists
   ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE;
   
   -- Create index
   CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code);
   
   -- Generate short codes for existing brokers
   UPDATE brokers 
   SET short_code = SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 4)
   WHERE short_code IS NULL;
   
   -- Update referral_link to use short format
   UPDATE brokers
   SET referral_link = 'https://liendeadline.com/r/' || short_code
   WHERE referral_link IS NULL OR referral_link NOT LIKE '/r/%';
   ```

   **Note:** This SQL approach uses random MD5 hashes, which:
   - May create collisions (you'll need to handle manually)
   - Doesn't use our ShortLinkGenerator logic
   - Less deterministic than email-based generation

---

## Option C: Railway Web Console

1. Go to Railway dashboard
2. Select your project
3. Open PostgreSQL database
4. Click "Query" tab
5. Paste and run:

```sql
-- Add column
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE;

-- Create index
CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code);

-- Generate codes (PostgreSQL)
UPDATE brokers 
SET short_code = SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 4)
WHERE short_code IS NULL;

-- Update links
UPDATE brokers
SET referral_link = 'https://liendeadline.com/r/' || short_code
WHERE referral_link IS NULL OR referral_link NOT LIKE '/r/%';
```

---

## Verification

After migration, verify with:

```sql
-- Check all brokers have short codes
SELECT id, email, name, short_code, referral_link 
FROM brokers 
ORDER BY created_at DESC;

-- Check for duplicates (should return 0 rows)
SELECT short_code, COUNT(*) 
FROM brokers 
GROUP BY short_code 
HAVING COUNT(*) > 1;
```

---

## Recommended Approach

**Use Option A (Python script)** because:
- ✅ Uses our ShortLinkGenerator class
- ✅ Handles collisions automatically
- ✅ Generates codes based on email (more deterministic)
- ✅ Updates referral_link automatically
- ✅ Better error handling
- ✅ Shows progress

---

## After Migration

1. **Test short links:**
   - Visit `https://liendeadline.com/r/{short_code}` for each broker
   - Verify redirect works
   - Check cookies are set

2. **Re-send welcome emails (optional):**
   - Can manually trigger from admin dashboard
   - Or brokers can find their link in dashboard

3. **Monitor:**
   - Check Railway logs for any errors
   - Verify click tracking works

