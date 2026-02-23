# Deployment Guide

> **Last Updated:** February 23, 2026

---

## Recent Deployments

| Date | Commit | Description |
|------|--------|-------------|
| Feb 23, 2026 | `cd377fb` | Repair cost tracking — vendor, cost, notes through full code path |
| Feb 23, 2026 | `78abb20` | SLA email notifications + Column mapping import + Streamlit 1.53.1 upgrade |
| Feb 16, 2026 | `de2511f` | Dashboard date range filters + Export to Excel on all data pages |
| Feb 16, 2026 | `b9b9e38` | **HOTFIX:** Revert all 50 remaining `width="stretch"` → `use_container_width=True` |
| Feb 16, 2026 | `525353a` | **HOTFIX:** Revert 3 `form_submit_button` `width="stretch"` (production crash) |
| Feb 12, 2026 | `22d467a` | Add Asset History Timeline with unified chronological view (P1) |
| Feb 12, 2026 | `d7ec010` | Fix Streamlit deprecation and pandas SQLAlchemy warnings (P0) |
| Feb 12, 2026 | `4556bea` | Extract auth & navigation from app.py into core/ modules (Step 8) |
| Feb 12, 2026 | `1748e18` | Fix Activity Log rendering raw HTML as code blocks |
| Feb 12, 2026 | `6cb802b` | Extract 13 page renderers from app.py into views/ package (Step 7) |
| Feb 12, 2026 | `0ca8d4f` | Extract reusable UI components from app.py (Step 6) |
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
□ Widget params use `use_container_width=True` (preferred over `width="stretch"`)
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
| Streamlit shows extra nav entries | Never use `pages/` directory name — Streamlit auto-detects it as multipage nav. Use `views/` instead |
| HTML rendered as raw text in `st.markdown()` | Avoid indented triple-quoted strings (4+ spaces = Markdown code block). Use string concatenation instead |
| Module changes not picked up after edit | Streamlit caches imported modules in `sys.modules`. Restart server: kill process, clear `__pycache__`, run fresh |
| `width="stretch"` crashes production | Production runs Streamlit 1.31.0 — use `use_container_width=True` only. Never use `width` param on widgets |

---

## Today's Changes (February 23, 2026)

### Repair Cost Tracking (`cd377fb`)
- **5 files changed:** `database/db.py`, `services/asset_service.py`, `views/quick_actions.py`, `views/issues_repairs.py`, `views/reports.py`
- **database/db.py:** Expanded `create_repair()` to INSERT `vendor_name` + `repair_cost`; added `update_repair()` with dynamic SET clause and `try/finally`; added `get_active_repair_by_asset_id()` to find active WITH_VENDOR repair; expanded `get_all_repairs()` SELECT with `repair_notes`
- **services/asset_service.py:** Added `update_repair_record()` and `get_active_repair_for_asset()` service wrappers with RBAC and cache invalidation
- **views/quick_actions.py:** Send to Vendor form now captures Vendor Name + Estimated Cost (3-column layout); Complete Repair now persists cost, notes, return date, status=COMPLETED to repair record
- **views/issues_repairs.py:** Repairs table expanded from 5 to 8 columns (Repair Reference, Serial Number, Vendor Name, Sent Date, Return Date, Status, Repair Cost, Repair Description); cost formatted as ₹X,XXX; fixed column name bug ("Received Date" → "Return Date")
- **views/reports.py:** Repair Analysis tab now shows Total Repair Cost, Avg Cost/Repair, Highest Repair, Repairs with Cost count, and Vendor Breakdown table (grouped by vendor with repair count + total cost)
- **DB migration required:** `ALTER TABLE repairs ADD COLUMN repair_notes TEXT AFTER repair_cost` and `ALTER TABLE repairs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER status`
- **No new dependencies or env vars**

### Streamlit Upgrade (`78abb20`)
- Upgraded `requirements.txt` from `streamlit==1.31.0` → `streamlit==1.53.1`
- Eliminates 22-version gap between local dev and production
- Previous `width="stretch"` hotfix no longer necessary (1.53.1 supports modern APIs)

### SLA Email Notifications (`78abb20`)
- **New file:** `services/email_service.py` — Gmail SMTP sender with HTML report builder
- Manual "Email SLA Report" button on Dashboard (Admin/Operations roles only)
- HTML email: dark header, 3-column summary (Critical/Warning/OK), asset table with badges, SLA thresholds footer
- Sends to all active Admin + Operations users with email addresses
- Requires `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` environment variables on Railway
- Button disabled with caption if env vars not configured
- Added `EMAIL_CONFIG` to `config/constants.py`
- Added `get_sla_breached_assets()` to `services/sla_service.py`

### Column Mapping Import (`78abb20`)
- **5-step flow:** Upload → Map Columns → Preview → Validate → Import
- Upload any Excel file (vendor invoices, procurement sheets, old IT registers)
- Auto-suggest: keyword matching across 18 app fields (case-insensitive, first match wins)
- Saved profiles: store/load/delete reusable mappings in `import_mapping_profiles` table (auto-created)
- Serial Number highlighted as required
- Duplicate protection in both auto-suggest (tracks used fields) and apply_column_mapping (deduplicates)
- DB functions use `try/finally` for guaranteed connection cleanup
- New utility functions in `database/excel_utils.py`: `detect_columns()`, `auto_suggest_mapping()`, `apply_column_mapping()`
- New DB functions in `database/db.py`: `get_import_profiles()`, `save_import_profile()`, `delete_import_profile()`

**Files changed (8):** `requirements.txt`, `config/constants.py`, `services/sla_service.py`, `services/email_service.py` (new), `views/dashboard.py`, `database/db.py`, `database/excel_utils.py`, `views/import_export.py`

---

## Previous Changes (February 16, 2026)

### Production Hotfix: `width="stretch"` Incompatibility
**Problem:** P0 fix (`d7ec010`) replaced `use_container_width=True` → `width="stretch"` across 53 widget calls. Production runs Streamlit 1.31.0 (pinned in `requirements.txt`) which does NOT support the `width` parameter on ANY widget. Local dev ran 1.53.1 where it works.

**Impact:** Production crashed on login page (`form_submit_button`) and dashboard (`st.button`). Two outages within hours.

**Fix (2 commits):**
1. `525353a` — Reverted 3 `st.form_submit_button` calls (incomplete — only fixed login)
2. `b9b9e38` — Reverted all 50 remaining `width="stretch"` across 9 files (full fix)

**Root Cause:** 22-version gap between local (1.53.1) and production (1.31.0). Local testing cannot catch API compatibility issues.

**Lesson Learned:** Always verify widget parameter compatibility against `requirements.txt` pinned version. Added to Common Issues table below.

### Dashboard Date Range Filters (`de2511f`)
**Feature:** Date range selector on Dashboard with preset options and Period Activity metrics.

**Date Range Selector (after Refresh button):**
- Presets: None (All Time), This Week, This Month, Last Month, Last 30 Days, Last 90 Days, Custom
- Custom mode shows two `st.date_input` pickers
- Clear button resets to All Time

**Period Activity Section (after Quick Actions):**
- Only appears when a date range is selected
- 5 KPI cards: New Assets (`created_at`), Assignments (`Shipment Date`), Returns (`Return Date`), Issues (`Reported Date`), Repairs (`Sent Date`)
- Uses existing `kpi-card` CSS classes

**Helper functions added:**
- `_get_date_presets()` — returns dict of preset name → (start_date, end_date)
- `_count_in_range(df, date_col, start, end)` — counts rows where date falls in range

**Files changed:** `views/dashboard.py` only

### Export to Excel — All Data Pages (`de2511f`)
**Feature:** Generic Excel export with formatted headers on all data pages.

**New function:** `export_dataframe_to_excel(df, sheet_name)` in `database/excel_utils.py`
- Orange headers (#F97316), white bold font, auto-width columns (max 50 chars)
- Frozen header row, thin borders on all cells
- Filters out internal `_id` columns, handles NaN → None
- Returns `BytesIO` buffer for `st.download_button`

**Pages updated with Excel + CSV side-by-side buttons:**
| Page | Data Exported |
|------|--------------|
| Assets | Filtered assets table |
| Assignments | Filtered assignments table |
| Issues & Repairs (Issues tab) | Filtered issues table |
| Issues & Repairs (Repairs tab) | Repairs table |
| Reports — Inventory | Full asset inventory |
| Reports — Billing Summary | Client billing breakdown |
| Reports — Repair Analysis | Repairs data |
| Billing | Billing summary table |

**Files changed:** `database/excel_utils.py`, `views/assets.py`, `views/billing.py`, `views/reports.py`, `views/assignments.py`, `views/issues_repairs.py`

---

## Previous Changes (February 12, 2026)

### Modular Architecture Extraction (Steps 1-8)
**Problem:** `app.py` was a monolith at 11,529 lines — all config, utilities, business logic, and UI in one file.

**Solution:** Extracted in 8 steps into 5 module layers with strict dependency rules:

| Layer | Files | Purpose | Lines |
|-------|-------|---------|-------|
| `config/` | `constants.py`, `styles.py`, `permissions.py` | Pure data, no runtime deps | ~700 |
| `core/` | `errors.py`, `data.py`, `auth.py`, `navigation.py` | Error handling, data, auth, sidebar | ~1,060 |
| `services/` | `billing_service.py`, `audit_service.py`, `asset_service.py`, `sla_service.py` | Business logic | ~813 |
| `components/` | `charts.py`, `empty_states.py`, `feedback.py`, `confirmation.py` | Reusable UI components | ~650 |
| `views/` | 13 page modules + `context.py` + `__init__.py` | Page renderers with AppContext dispatch | ~5,500 |

**Result:** app.py reduced from 11,529 → ~230 lines (98% reduction). Extraction complete.

**Key commits:**
- `73144f5` — Steps 1-5: config/, core/, services/ extraction
- `0ca8d4f` — Step 6: components/ extraction (charts, empty states, feedback, confirmation)
- `6cb802b` — Step 7: views/ extraction (13 page renderers + AppContext pattern)
- `4556bea` — Step 8: core/auth.py + core/navigation.py extraction (auth, login page, sidebar, footer)

**Key decisions:**
- No logic changes — functions copied exactly as-is
- Database functions imported with `try/except ImportError` pattern in services and core/auth
- Named `views/` not `pages/` — Streamlit auto-detects `pages/` as multipage nav
- AppContext dataclass bundles shared state; each page exports `render(ctx)` function
- `PAGE_REGISTRY` dict maps page display names → render functions for dispatch
- `core/auth.py` manages its own `_AUTH_AVAILABLE` flag via `try/except ImportError` from `database.auth`
- `core/navigation.py` exposes `render_sidebar(db_connected) -> str` returning current page name
- Also fixed `classify_error`/`USER_SAFE_MESSAGES` missing import bug, removed 30+ dead MySQL imports

### P0: Fix Deprecation Warnings — ⚠️ Partially Reverted
**Problem:** Console flooded with Streamlit `use_container_width` deprecation warnings and pandas SQLAlchemy warnings on every page load.

**Solution:**
1. Replaced `use_container_width=True` → `width="stretch"` across 10 files (53 replacements) — `commit d7ec010`
2. **REVERTED:** `width="stretch"` back to `use_container_width=True` — production Streamlit 1.31.0 doesn't support `width` param (`525353a`, `b9b9e38`)
3. Added `_query_to_df()` cursor-based helper in `database/db.py`, replaced all 8 `pd.read_sql()` calls — eliminates pandas SQLAlchemy warning ← this part remains

**Result:** pandas SQLAlchemy warnings eliminated. Streamlit deprecation warnings persist until production version is upgraded.

### P1: Asset History Timeline
**Problem:** "View Asset History" section in Assets page only showed assignments and issues as separate static dataframes. No repairs, no activity log, no chronological view.

**Solution:** Replaced with unified timeline merging 4 data sources chronologically — `commit 22d467a`

**Data sources:**
- `ctx.assignments_df` (client-side filter by serial) → Blue 📦 cards
- `ctx.issues_df` (client-side filter by serial) → Red ⚠ cards
- `ctx.repairs_df` (client-side filter by serial) → Orange 🔧 cards
- `get_activity_log(asset_id=N)` (server-side query) → Gray 📋 cards

**Features:**
- Color-coded cards with left border per event type
- Event limit selector (50/100/200)
- Summary bar: "12 events: 3 Assignments, 2 Issues, 1 Repair, 6 Activities"
- Most recent first chronological sort
- Empty state when no history found

**Files changed:** `views/assets.py` only (added 2 helper functions, replaced expander content)

### Activity Log HTML Rendering Fix
**Problem:** Activity Log page showed raw HTML tags as text instead of rendering them.

**Root Cause:** Indented triple-quoted f-strings had 4+ leading spaces, which `st.markdown()` treats as Markdown code blocks (preformatted text).

**Solution:** Replaced indented triple-quoted strings with parenthesized string concatenation (zero leading whitespace) — `commit 1748e18`.

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
