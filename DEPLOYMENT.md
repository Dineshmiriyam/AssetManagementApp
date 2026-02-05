# Deployment Guide

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

---

## Emergency Contacts

- **Railway Status:** https://status.railway.app
- **Railway Support:** Through dashboard
