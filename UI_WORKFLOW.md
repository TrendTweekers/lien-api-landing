# Dashboard UI Workflow Guide

## ⚠️ CRITICAL: Which Dashboard Files to Edit

### ✅ REAL Dashboard UI (Source of Truth)

**Location:** `dashboard/`

**These files contain the actual product dashboard:**
- `dashboard/src/pages/` - Dashboard pages
- `dashboard/src/components/` - React components
- `dashboard/src/pages/PopularZaps.tsx` - Zapier setup UI
- `dashboard/src/components/dashboard/NotificationSettings.tsx` - Notification settings UI
- `dashboard/src/components/dashboard/IntegrationsSection.tsx` - Integrations UI

**Accessible at:** `/dashboard/*` (served by FastAPI SPA routing)

### ❌ Legacy Static Files (DO NOT EDIT)

**Location:** Repository root

**These files are legacy and should NOT receive product UI changes:**
- `dashboard.html` - Legacy static dashboard
- `dashboard.js` - Legacy static dashboard JavaScript

**Why they exist:** Backwards compatibility, legacy routes

**When to edit:** Only for critical security fixes or legacy compatibility maintenance, and only with `[legacy-ok]` in commit message.

---

## 🚨 Strict Rule

**Dashboard UI changes happen ONLY in `dashboard/`**

If you're asked to make a dashboard UI change and the file is NOT under `dashboard/`, **STOP** and report:
- "This file is legacy. The real dashboard UI is in `dashboard/`"
- Point to the correct file location

---

## 🔄 Quick Checklist: Revert Accidental Edits

If you accidentally edited `dashboard.html` or `dashboard.js`:

```bash
# Check what changed
git status

# Revert the legacy files
git checkout -- dashboard.html dashboard.js

# Verify the real dashboard files are still correct
git status
```

---

## 📝 Pre-commit Guard

A pre-commit hook prevents accidental commits to legacy files.

**To enable:**
```bash
# Copy the guard script to .git/hooks/
cp scripts/precommit_guard.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**How it works:**
- Blocks commits if `dashboard.html` or `dashboard.js` changed
- Allows commit if message contains `[legacy-ok]`
- Shows clear error message pointing to correct files

**To bypass (only for legitimate legacy fixes):**
```bash
git commit -m "fix: critical security fix [legacy-ok]"
```

---

## 🗺️ File Map

| What You Want to Change | Edit This File |
|------------------------|----------------|
| Zapier setup UI | `dashboard/src/pages/PopularZaps.tsx` |
| Notification settings | `dashboard/src/components/dashboard/NotificationSettings.tsx` |
| Integrations section | `dashboard/src/components/dashboard/IntegrationsSection.tsx` |
| Projects table | `dashboard/src/components/dashboard/ProjectsTable.tsx` |
| Main dashboard page | `dashboard/src/pages/Index.tsx` |
| Legacy compatibility | `dashboard.html` / `dashboard.js` (with `[legacy-ok]`) |

---

## 🎯 Common Mistakes

### ❌ Wrong: Editing `dashboard.html` for new features
```bash
# DON'T DO THIS
vim dashboard.html  # Adding Zapier token UI here
```

### ✅ Right: Editing React components
```bash
# DO THIS INSTEAD
vim dashboard/src/pages/PopularZaps.tsx
```

---

## 📚 Related Documentation

- See `DEV_NOTES.md` for development setup
- See `ZAPIER_INTEGRATION_GUIDE.md` for Zapier integration details

