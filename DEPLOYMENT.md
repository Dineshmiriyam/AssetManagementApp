# Deployment Guide

> **Last Updated:** February 6, 2026

---

## Recent Deployments

| Date | Commit | Description |
|------|--------|-------------|
| Feb 6, 2026 | `0bfcd0a` | Fix Notes text area border visibility |
| Feb 6, 2026 | `357a0ec` | Fix login loop and improve dashboard card UX |

---

## Quick Deploy (90% of cases)

```bash
# 1. Check what changed
git status

# 2. Add changes
git add app.py

# 3. Commit with message
git commit -m "Brief description of what changed"

# 4. Push to GitHub
git push origin main

# 5. Wait 2 minutes for Railway auto-deploy

# 6. Hard refresh browser
# Press Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
```

---

## Pre-Deployment Checklist

```
□ Tested locally with `streamlit run app.py`
□ No Python syntax errors
□ No console errors in browser
□ Feature works as expected
□ Other features still work
```

---

## Verify Deployment

### Check Railway Dashboard
1. Go to https://railway.app/dashboard
2. Click your project
3. Check deployment status (should be green/success)
4. View logs if there's an error

### Check Live App
1. Open your app URL
2. Press Ctrl+Shift+R (hard refresh)
3. Test the changed feature
4. Verify nothing else broke

---

## Rollback (If Something Breaks)

```bash
# See recent commits
git log --oneline -5

# Revert to previous commit
git revert HEAD

# Push the revert
git push origin main
```

---

## Environment Variables

If you need to add/change environment variables:

1. Go to Railway dashboard
2. Click your project
3. Go to Variables tab
4. Add/edit variable
5. Railway will auto-redeploy

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Changes not appearing | Hard refresh (Ctrl+Shift+R) |
| "Module not found" error | Add to requirements.txt, push again |
| Database connection error | Check Railway MySQL is running |
| App won't start | Check Railway logs for error |
| Old version still showing | Wait 2 min, Railway is still deploying |
| Login loop after clicking cards | Check for `<a href>` tags - use `st.button()` instead |
| Buttons visible below cards | CSS merged design should hide them - check CSS loaded |
| Input fields have no border | Check CSS border color is visible (use `#cbd5e1` not `#e2e8f0`) |

---

## Today's Fixes (February 6, 2026)

### Login Loop Fix
**Problem:** Clicking dashboard cards redirected to login in infinite loop

**Root Cause:** Anchor tags (`<a href="?nav=...">`) caused full page reload, losing session state

**Solution:**
- Replaced all anchor tags with `st.button()`
- Added safety check after session validation
- Navigation now uses `st.session_state.current_page`

### Dashboard Card UX
**Problem:** Small "View" buttons appeared disconnected below cards

**Solution:** Merged card+button design
- Card: bottom border-radius removed
- Button: styled as card footer with rounded bottom
- Hover: both lift together

### Notes Field Border
**Problem:** Text area in Add Asset had invisible border

**Solution:** Changed border color from `#e2e8f0` to `#cbd5e1`

---

## Emergency Contacts

- **Railway Status:** https://status.railway.app
- **Railway Support:** Through dashboard
