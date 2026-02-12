# Deployment Guide

> **Last Updated:** February 12, 2026

---

## Recent Deployments

| Date | Commit | Description |
|------|--------|-------------|
| Feb 12, 2026 | `73144f5` | Extract modular architecture from app.py (Steps 1-5) |
| Feb 11, 2026 | `6e65c40` | Fix compressed login page after logout on production |
| Feb 11, 2026 | `629de8d` | Fix session token not persisting in production URL |
| Feb 11, 2026 | `0b91f13` | Fix compressed login page after logout |
| Feb 11, 2026 | `703e184` | Fix sidebar missing — simplify anti-flicker CSS |
| Feb 11, 2026 | `baaba6d` | Revert sidebar to expanded (fix missing menu) |
| Feb 11, 2026 | `0fdbe8b` | Anti-flicker overhaul, session restore optimization, exception handling |
| Feb 10, 2026 | `4513d47` | Add Retired Assets (Sold/Disposed) KPI cards to Dashboard |
| Feb 10, 2026 | `2201308` | Fix duplicate clients in Select Client dropdown |
| Feb 10, 2026 | `18810ea` | Fix session persistence on hard refresh and sidebar visibility |
| Feb 10, 2026 | `b052235` | Enhance pagination with centered layout and active page styling |
| Feb 10, 2026 | `234f2bd` | Add page navigation buttons to all paginated tables |
| Feb 10, 2026 | `e1a8fd7` | Enhance Assets page with search form, summary badges, quick actions |
| Feb 6, 2026 | `b144729` | Fix bulk selection clear error in Assets page |
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
| Widget state modification error | Use callback + flag pattern (see GUARDRAILS.md) |
| Railway webhook missed deploy | Push empty trigger commit: `git commit --allow-empty -m "trigger deploy"` |
| Login lost on hard refresh (prod) | Session token persisted in `st.query_params` - auto-restores on refresh |
| Sidebar hidden after login (prod) | Changed `initial_sidebar_state` to `"expanded"` |
| Sidebar missing after CSS changes | Anti-flicker CSS must only use `display: none` on sidebar — no `width: 0` or `min-width: 0` |
| Login page compressed after logout | Add `section.main { width: 100%; margin-left: 0 }` to login CSS |
| Session token not in URL (production) | Move `st.query_params` out of silent `try/except` — call directly from handler |
| Login page compressed after logout (prod) | Move `st.query_params.clear()` out of `logout_user()` — call directly from sign out handler |
| `KeyError: None` on logout | `st.query_params.clear()` doesn't stop execution — add `safe_rerun()` after it |
| Duplicate items in dropdowns | Use `.dropna().unique().tolist()` not just `.tolist()` |

---

## Today's Changes (February 12, 2026)

### Modular Architecture Extraction (Steps 1-5)
**Problem:** `app.py` was a monolith at 11,529 lines — all config, utilities, business logic, and UI in one file.

**Solution:** Extracted into 3 module layers with strict dependency rules:

| Layer | Files | Purpose | Lines |
|-------|-------|---------|-------|
| `config/` | `constants.py`, `styles.py`, `permissions.py` | Pure data, no runtime deps | ~700 |
| `core/` | `errors.py`, `data.py` | Error handling, data fetching, pagination, caching | ~600 |
| `services/` | `billing_service.py`, `audit_service.py`, `asset_service.py`, `sla_service.py` | Business logic | ~813 |

**Result:** app.py reduced from 11,529 → 7,150 lines (38% reduction).

**Key decisions:**
- No logic changes — functions copied exactly as-is
- Database functions imported with `try/except ImportError` pattern in services
- `DATA_SOURCE` read from `os.getenv` in service modules (same as app.py)
- Constants `VALID_INITIAL_STATUSES` and `CRITICAL_ACTIONS` moved to `config/constants.py`

**Remaining work (Steps 6-8):** UI components, page renderers, auth/navigation still in app.py.

---

## Previous Changes (February 11, 2026)

### Anti-Flicker CSS Overhaul
**Problem:** Login page flashed on refresh; page appeared compressed during auth check

**Root Cause:** Old `fadeIn` animation was insufficient. Sidebar still visible before CSS loaded.

**Solution:** New approach using `.stApp { opacity: 0 !important }` in anti-flicker CSS:
- Hides entire app until auth decision is made
- Login page CSS sets `opacity: 1` to reveal login form
- Dashboard CSS sets `opacity: 1` to reveal dashboard + sidebar
- Anti-flicker sidebar CSS uses only `display: none` (no width/min-width overrides)

### Session Restore Optimization
**Problem:** `login_user()` re-set `st.query_params["sid"]` during restore, causing potential unnecessary rerun

**Solution:** Added `from_restore=False` parameter. Session restoration passes `True` to skip query_params (already in URL).

### Exception Handling Improvement
**Problem:** All exceptions during session validation deleted sid from URL, including network timeouts

**Solution:** Split handlers:
- `ValueError` (malformed sid) → clear sid from URL
- General `Exception` (network/DB error) → keep sid for retry on next load

### Login Page Compressed After Logout
**Problem:** Login form appeared compressed after logout because Streamlit's inline sidebar margin was still active

**Solution:** Added to login page CSS:
```css
section.main { width: 100% !important; margin-left: 0 !important; }
```

### Session Token Not Persisting on Production (NEW)
**Problem:** After login on production, `?sid=` token was NOT appearing in the URL, even though it worked on localhost. Session persistence was completely broken on production.

**Root Cause:** `st.query_params["sid"] = value` inside `login_user()` was wrapped in `try/except Exception: pass`, which silently caught a production-specific error. The error was invisible because of the silent catch.

**Solution:** Same pattern applied to both `login_user()` and `logout_user()`:
1. Removed `st.query_params` operations from inside the functions
2. Moved them to the calling handlers (login form handler, sign out button handler)
3. Called directly without silent `try/except Exception: pass`
4. Added `logger.info/warning/error` for visibility

### Compressed Login Page on Production After Logout (NEW)
**Problem:** Login page appeared compressed ONLY on production after logout, not on localhost.

**Root Cause:** Same silent `try/except Exception: pass` pattern in `logout_user()`. On production, `del st.query_params["sid"]` failed silently → `?sid=` stayed in URL → session restore code ran with failed `st.query_params` operations → Streamlit rendering left in inconsistent state.

**Solution:**
1. Removed `st.query_params.clear()` from `logout_user()` (caller handles it)
2. Sign out button calls `st.query_params.clear()` directly then `safe_rerun()`
3. Session restore uses `_clear_sid` flag — calls `st.query_params.clear()` OUTSIDE `try/except`
4. Broadened login CSS to override `[data-testid="stMain"]` and `.stMainBlockContainer`

### Lesson Learned: `st.query_params` on Production
**NEVER** wrap `st.query_params` operations in `try/except Exception: pass`. On Railway production, these operations can fail silently due to reverse proxy or Streamlit version behavior. Always call them directly from the handler and log errors.

**Pattern:** Same as Streamlit widget callbacks — `login_user()`/`logout_user()` handle state only. Callers handle `st.query_params` directly.

### Lesson Learned: `st.query_params` Does NOT Stop Execution
`st.query_params.clear()` and `st.query_params["key"] = value` queue a rerun but do NOT stop script execution. If session state was already cleared (e.g., `logout_user()` set `user_role = None`), the remaining script will crash (`KeyError: None`). Always call `safe_rerun()` after if the script must not continue.

### Lesson Learned: CSS Cascade Conflicts
Anti-flicker CSS must be MINIMAL — only set properties that the dashboard/login CSS explicitly overrides. Setting `width: 0` and `min-width: 0` on the sidebar caused them to persist because dashboard CSS only overrode `display` and `visibility`.

---

## Previous Changes (February 10, 2026)

### Session Persistence on Hard Refresh
**Problem:** Hard refresh on production showed login page (session state lost)

**Root Cause:** Streamlit session state is in-memory, tied to WebSocket. Hard refresh kills WebSocket = new session = logged out.

**Solution:** Persist session token in URL via `st.query_params`
- After login: `st.query_params["sid"] = f"{user_id}:{session_token}"`
- On page load: Check `sid` param, call `validate_session()` to restore session
- On logout: Clear `sid` from URL
- Uses existing DB token infrastructure (`session_token_hash` column)

### Sidebar Visibility Fix
**Problem:** Sidebar menu hidden on production, required clicking ">" arrow

**Root Cause:** `initial_sidebar_state="collapsed"` in `st.set_page_config()`

**Solution:** Changed to `"expanded"`. Login page CSS already hides sidebar independently.

### Login Page Anti-Flicker
**Problem:** Login page elements visually shifted during rendering

**Solution:**
- Added CSS `fadeIn` animation (0.25s) on `.main .block-container`
- Added `min-height: 80px` on login brand section to reserve space for logo

### Duplicate Clients in Dropdown
**Problem:** Select Client dropdown showed duplicate entries (Judigo x3, Ram Home x3)

**Root Cause:** Production `clients` table had duplicate records from multiple imports. Code used `.tolist()` without deduplication.

**Solution:**
- Code: Changed to `.dropna().unique().tolist()` in Quick Actions assign form
- Database: Deleted 6 duplicate client records, kept originals (ids 1, 2, 3)

### Asset Location Data Fix
**Problem:** 4 assets had `current_location = 'With_Client'` (status text) instead of actual client name

**Root Cause:** Excel import stored status text as location

**Solution:** SQL UPDATE on production: `SET current_location = 'X3i Solution' WHERE current_location = 'With_Client'`

### Assets Page Enhancements
- Orange Search button + ghost Clear Filters button (wrapped in `st.form`)
- Summary status badges below page header
- Active filter indicator pills
- Table column reorder (Serial, Brand, Model, Status, Location first)
- Export CSV moved to top-right
- Per-row quick actions panel (expander)

### Pagination Navigation
- Page number buttons (1, 2, 3...) below all 6 tables
- Active page highlighted with orange gradient
- Centered layout with "Page X of Y" text
- Applied to: Assets, Assignments, Issues, Repairs, Clients, Export Preview

### Retired Assets KPI Cards
**Feature:** New "RETIRED ASSETS" section on Dashboard below Inventory Overview
- Sold card (purple, #8b5cf6) with "View Sold" navigation
- Disposed card (gray, #6b7280) with "View Disposed" navigation
- Same merged card+button pattern as existing 5 KPI cards

### Database Sync
- Synced localhost database from production (source of truth)
- Both databases now identical (59 assets, 3 clients, 2 users)

---

## Previous Fixes (February 6, 2026)

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

### Bulk Selection Clear Error
**Problem:** Clicking "Clear Selection" in Assets page caused StreamlitAPIException

**Root Cause:** Cannot modify `st.session_state.bulk_asset_select` after multiselect widget instantiated

**Solution:** Callback + flag pattern
- Button uses `on_click` callback to set `clear_bulk_selection_flag = True`
- Flag checked BEFORE multiselect widget renders
- If flag is True, clear selection and reset flag

---

## Emergency Contacts

- **Railway Status:** https://status.railway.app
- **Railway Support:** Through dashboard
