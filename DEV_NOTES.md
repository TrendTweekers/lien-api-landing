# Development Notes

## 🚨 Critical: Dashboard UI Files

### ⚠️ Common Mistake: Editing Wrong Dashboard Files

**DO NOT edit `dashboard.html` or `dashboard.js` for product UI changes.**

These are legacy static files. The real dashboard UI is in:
- `dashboard-v2/deadline-glow-up-main/src/`

### How to Revert Accidental Edits

If you accidentally edited legacy files:

```bash
# Check what changed
git status

# Revert the legacy files
git checkout -- dashboard.html dashboard.js
```

---

## Pre-commit Guard

A pre-commit hook prevents accidental commits to legacy dashboard files.

### Enable the Guard

```bash
# Copy the guard script to .git/hooks/
cp scripts/precommit_guard.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### How It Works

- **Blocks commits** if `dashboard.html` or `dashboard.js` changed
- **Allows commit** if message contains `[legacy-ok]`
- Shows clear error message pointing to correct files

### Bypass (Only for Legitimate Legacy Fixes)

If you need to edit legacy files for critical fixes:

```bash
git commit -m "fix: critical security fix [legacy-ok]"
```

---

## File Structure

### Real Dashboard (Edit These)
- `dashboard-v2/deadline-glow-up-main/src/pages/` - Dashboard pages
- `dashboard-v2/deadline-glow-up-main/src/components/` - React components
- Served at `/dashboard/*` via FastAPI SPA routing

### Legacy Files (Don't Edit)
- `dashboard.html` - Legacy static dashboard
- `dashboard.js` - Legacy static dashboard JavaScript

---

## See Also

- `UI_WORKFLOW.md` - Detailed workflow guide
- `ZAPIER_INTEGRATION_GUIDE.md` - Zapier integration details

