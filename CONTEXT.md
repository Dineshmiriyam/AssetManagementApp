# NXTBY Asset Management System - Project Context

> **Last Updated:** February 23, 2026
> **Version:** 2.2
> **Status:** Production (Internal Use)

---

## 1. PROJECT OVERVIEW

### What Is This?
An internal IT Asset Management System for tracking laptops and other IT equipment through their complete lifecycle - from purchase to deployment to retirement.

### Who Uses It?
- **Internal Team:** 5+ users
- **Roles:** Admin, Operations, Finance
- **Purpose:** Internal tool (not for external customers)

### Business Problem Solved
- Track where every asset is at any time
- Know which assets are with which clients
- Monitor SLA compliance for returns/repairs
- Calculate billing based on deployed assets
- Maintain audit trail for all actions

---

## 2. TECH STACK

| Layer | Technology | Why Chosen |
|-------|------------|------------|
| **Frontend** | Streamlit (Python) | Fast development, Python-only |
| **Database** | MySQL | Reliable, scalable, industry standard |
| **Hosting** | Railway | Easy deployment, auto-deploy from GitHub |
| **Version Control** | GitHub | Industry standard |
| **Authentication** | Custom (bcrypt) | Simple, secure password hashing |

### Dependencies (requirements.txt)
```
streamlit==1.53.1
pyairtable==2.2.1        # Legacy - was used before MySQL
pandas==2.1.4
plotly==5.18.0
python-dotenv==1.0.0
streamlit-plotly-events==0.0.6
mysql-connector-python==9.5.0
bcrypt==4.1.2
openpyxl==3.1.2
qrcode[pil]==7.4.2
Pillow==10.2.0
reportlab==4.1.0
```

---

## 3. ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                        USERS                                 │
│              (Admin, Operations, Finance)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT APP                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  app.py (orchestration only, ~230 lines)              │   │
│  └──────────┬───────────────────────────────────────────┘   │
│             │ imports                                        │
│  ┌──────────┴───────────────────────────────────────────┐   │
│  │  views/           (13 page renderers)                 │   │
│  │  ├ context.py     AppContext dataclass                 │   │
│  │  ├ dashboard.py   billing.py     activity_log.py      │   │
│  │  ├ assets.py      reports.py     user_management.py   │   │
│  │  ├ quick_actions.py  clients.py  import_export.py     │   │
│  │  ├ add_asset.py   assignments.py settings.py          │   │
│  │  └ issues_repairs.py                                  │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  components/      (reusable UI)                       │   │
│  │  ├ charts.py      Analytics bar/donut/gauge charts    │   │
│  │  ├ empty_states.py  Zero-data placeholders            │   │
│  │  ├ feedback.py    Status badges, alerts, errors       │   │
│  │  └ confirmation.py  Action confirmation dialogs       │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  config/        │  core/          │  services/        │   │
│  │  ├ constants.py │  ├ errors.py    │  ├ billing_svc.py │   │
│  │  ├ styles.py    │  ├ data.py      │  ├ audit_svc.py   │   │
│  │  └ permissions  │  ├ auth.py      │  ├ asset_svc.py   │   │
│  │                 │  └ navigation   │  ├ sla_svc.py     │   │
│  │                 │                 │  └ email_svc.py    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MySQL DATABASE                            │
│                     (Railway)                                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ assets │clients│ users │activity│assign-│ import_ │  │
│  │        │       │       │  _log  │ ments │mapping_ │  │
│  │        │       │       │        │       │profiles │  │
│  └────────┴───────┴───────┴────────┴───────┴─────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Module Dependency Rules
```
config/     → depends on NOTHING (pure data)
core/       → depends on config/, database/
services/   → depends on config/, core/, database/
components/ → depends on config/, services/ (UI helpers)
views/      → depends on everything above (page renderers)
app.py      → depends on views/, config/, core/ (orchestration only)
```
Lower layers never import from higher layers. `views/` uses the `AppContext` dataclass pattern — each page module exports a `render(ctx)` function.

---

## 4. USER ROLES & PERMISSIONS

### Role Matrix

| Feature | Admin | Operations | Finance |
|---------|:-----:|:----------:|:-------:|
| View Dashboard | ✅ | ✅ | ✅ |
| View All Assets | ✅ | ✅ | ✅ |
| Add New Asset | ✅ | ❌ | ❌ |
| Edit Asset | ✅ | ✅ | ❌ |
| Delete Asset | ✅ | ❌ | ❌ |
| Assign to Client | ✅ | ✅ | ❌ |
| Receive Returns | ✅ | ✅ | ❌ |
| Send to Repair | ✅ | ✅ | ❌ |
| View Billing | ✅ | ❌ | ✅ |
| Close Billing Period | ✅ | ❌ | ✅ |
| Manage Users | ✅ | ❌ | ❌ |
| View Activity Log | ✅ | ✅ | ✅ |
| Import Assets | ✅ | ❌ | ❌ |
| Generate QR Codes | ✅ | ✅ | ✅ |

### Role Focus Areas
- **Admin:** Full access, system configuration, user management
- **Operations:** Day-to-day asset lifecycle, assignments, repairs
- **Finance:** Billing, revenue tracking, financial reports

---

## 5. ASSET LIFECYCLE

```
                    ┌─────────────────┐
                    │  IN_STOCK_NEW   │ (Just purchased)
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │IN_STOCK_WORKING │ (Ready to deploy)
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌─────────────┐  ┌───────────┐  ┌───────────────┐
     │ WITH_CLIENT │  │   SOLD    │  │IN_OFFICE_TEST │
     └──────┬──────┘  └───────────┘  └───────┬───────┘
            │                                │
            ▼                                │
┌───────────────────────┐                    │
│ RETURNED_FROM_CLIENT  │◄───────────────────┘
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  WITH_VENDOR_REPAIR   │
└───────────┬───────────┘
            │
            ▼
   ┌─────────────────┐
   │IN_STOCK_WORKING │ (Back in rotation)
   └─────────────────┘
```

### Status Definitions

| Status | Meaning | Billable? |
|--------|---------|:---------:|
| IN_STOCK_NEW | Just purchased, not yet configured | No |
| IN_STOCK_WORKING | Ready to deploy to client | No |
| WITH_CLIENT | Deployed and generating revenue | **Yes** |
| RETURNED_FROM_CLIENT | Came back, needs inspection | No |
| IN_OFFICE_TESTING | Being tested/configured | No |
| WITH_VENDOR_REPAIR | Sent for repair | No |
| SOLD | Permanently sold | No |

---

## 6. COMPLETED FEATURES

### Dashboard
- [x] Role-based views (Admin/Operations/Finance see different data)
- [x] KPI cards (Total, Deployed, Available, In Repair, Returned)
- [x] Retired Assets KPI cards (Sold, Disposed) in separate section
- [x] KPI cards clickable - navigate to filtered Assets page
- [x] SLA indicators (Critical, Warning, OK)
- [x] Revenue metrics (Admin/Finance only)
- [x] Interactive charts (click to filter)
- [x] Quick action buttons
- [x] Date range filters with presets (This Week, This Month, Last Month, Last 30/90 Days, Custom)
- [x] Period Activity section (time-filtered counts: New Assets, Assignments, Returns, Issues, Repairs)

### Assets Page
- [x] View all assets with filters
- [x] Search by serial number, brand, model (wrapped in st.form)
- [x] Filter by status, brand, type, location
- [x] Summary status badges below header
- [x] Active filter indicator pills
- [x] Bulk operations (select multiple, change status, assign)
- [x] Individual asset actions (Fix, Send to Vendor)
- [x] Per-row quick actions panel
- [x] SLA filter integration
- [x] Linked record navigation
- [x] Asset History Timeline (unified chronological view of assignments, issues, repairs, activity log)
- [x] Page navigation buttons (1, 2, 3...) below table
- [x] Export CSV button at top-right
- [x] Export to Excel (formatted, orange headers) + CSV side-by-side

### Quick Actions
- [x] Assign asset to client
- [x] Receive return from client
- [x] Send to vendor for repair
- [x] Complete repair
- [x] Add new asset

### Clients Page
- [x] View all clients
- [x] Add new client
- [x] View client's assigned assets

### Assignments Page
- [x] View all assignments
- [x] Track shipment dates
- [x] View assignment history

### Issues Page
- [x] Track asset issues
- [x] Link issues to assets

### Billing Page
- [x] View billable assets
- [x] Calculate monthly revenue
- [x] Billing period management
- [x] Close/reopen periods

### Activity Log
- [x] Track all user actions
- [x] Filter by action type
- [x] Audit trail for compliance

### Settings
- [x] User management (Admin only)
- [x] Add/edit users
- [x] Role assignment
- [x] Password reset
- [x] SLA threshold configuration

### Other Features
- [x] QR code generation (single and bulk PDF)
- [x] Excel import with column mapping (upload any Excel, auto-suggest mapping, save profiles)
- [x] Export to Excel on all data pages (Assets, Assignments, Issues, Repairs, Reports, Billing) — formatted with orange headers, auto-width columns
- [x] SLA email notifications (Gmail SMTP, manual trigger, Admin/Operations only)
- [x] Session management with token persistence (survives hard refresh)
- [x] Login/logout with activity logging
- [x] Pagination navigation on all tables (Assets, Assignments, Issues, Repairs, Clients, Export)

---

## 7. PLANNED FEATURES (Priority Order)

### High Priority
- [x] Asset history timeline (view all changes to an asset) — `22d467a`
- [x] Dashboard date range filters — `de2511f`
- [x] Export to Excel (filtered data) — `de2511f`
- [x] Email notifications (SLA alerts) — `78abb20`
- [x] Column mapping import (upload any Excel format) — `78abb20`
- [x] Streamlit upgrade 1.31.0 → 1.53.1 — `78abb20`

### Medium Priority
- [ ] Asset photos/attachments
- [ ] Client contact management
- [ ] Repair cost tracking
- [ ] Custom reports

### Low Priority
- [ ] Mobile-optimized views
- [ ] API for integrations
- [ ] Multi-company support
- [ ] Barcode (in addition to QR) support

---

## 8. DATABASE SCHEMA (Key Tables)

### assets
```sql
- id (INT, PK)
- serial_number (VARCHAR, UNIQUE)
- asset_type (VARCHAR)
- brand (VARCHAR)
- model (VARCHAR)
- current_status (VARCHAR)
- current_location (VARCHAR)
- current_client_id (INT, FK)
- purchase_date (DATE)
- specs (TEXT)
- notes (TEXT)
- created_at (DATETIME)
- updated_at (DATETIME)
```

### clients
```sql
- id (INT, PK)
- client_name (VARCHAR)
- contact_person (VARCHAR)
- email (VARCHAR)
- phone (VARCHAR)
- address (TEXT)
- created_at (DATETIME)
```

### users
```sql
- id (INT, PK)
- username (VARCHAR, UNIQUE)
- email (VARCHAR)
- password_hash (VARCHAR)
- role (VARCHAR)
- full_name (VARCHAR)
- is_active (BOOLEAN)
- created_at (DATETIME)
```

### assignments
```sql
- id (INT, PK)
- asset_id (INT, FK)
- client_id (INT, FK)
- assigned_date (DATE)
- returned_date (DATE)
- status (VARCHAR)
- notes (TEXT)
```

### activity_log
```sql
- id (INT, PK)
- user_id (INT, FK)
- action_type (VARCHAR)
- category (VARCHAR)
- description (TEXT)
- asset_id (INT, FK, nullable)
- metadata (JSON)
- created_at (DATETIME)
```

### import_mapping_profiles
```sql
- id (INT, PK, AUTO_INCREMENT)
- profile_name (VARCHAR(100), UNIQUE)
- mapping (JSON)
- created_by (VARCHAR(50))
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

---

## 9. FILE STRUCTURE

```
AssetManagementApp/
├── app.py                 # Orchestration: page config + data loading + dispatch (~230 lines)
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (DO NOT COMMIT)
├── .gitignore
├── CONTEXT.md            # This file
├── GUARDRAILS.md         # Development rules
├── DEPLOYMENT.md         # Deployment checklist
├── README.md
│
├── views/                # Page renderers (13 pages, ~5,500 lines total)
│   ├── __init__.py       # PAGE_REGISTRY dict mapping page names → render functions
│   ├── context.py        # AppContext dataclass (shared state for all pages)
│   ├── dashboard.py      # Dashboard analytics, KPIs, role-based sections
│   ├── assets.py         # Asset inventory, filters, bulk operations
│   ├── quick_actions.py  # State transitions with confirmation dialogs
│   ├── add_asset.py      # Asset creation form
│   ├── assignments.py    # Assignment tracking and history
│   ├── issues_repairs.py # Issues & repairs management
│   ├── clients.py        # Client directory
│   ├── reports.py        # Analytics reports
│   ├── billing.py        # Billing period management
│   ├── activity_log.py   # Audit trail and event history
│   ├── user_management.py # User CRUD (admin only)
│   ├── import_export.py  # CSV import, Excel export, QR codes
│   └── settings.py       # System configuration, RBAC display
│
├── components/           # Reusable UI components
│   ├── __init__.py
│   ├── charts.py         # Analytics bar, donut, gauge charts (Plotly)
│   ├── empty_states.py   # Zero-data placeholder messages
│   ├── feedback.py       # Status badges, billing badges, inline alerts
│   └── confirmation.py   # Action confirmation dialog pattern
│
├── config/               # Pure data configuration (no runtime deps)
│   ├── __init__.py
│   ├── constants.py      # All constants, status configs, billing config, form options
│   ├── styles.py         # CSS (anti-flicker, login, dashboard)
│   └── permissions.py    # RBAC system, role permissions, action validation
│
├── core/                 # Shared utilities
│   ├── __init__.py
│   ├── errors.py         # Error handling, logging, user-safe messages
│   ├── data.py           # Data fetching, pagination, caching
│   ├── auth.py           # Auth session management, login page, session restore
│   └── navigation.py     # Sidebar navigation, menu config, footer
│
├── services/             # Business logic
│   ├── __init__.py
│   ├── billing_service.py  # Billing status, metrics, impact calculations
│   ├── audit_service.py    # Audit trail, activity logging, state changes
│   ├── asset_service.py    # Asset CRUD, status transitions, RBAC validation
│   ├── sla_service.py      # SLA calculations, role-based filtering
│   └── email_service.py    # Gmail SMTP SLA report sender
│
├── database/
│   ├── db.py             # MySQL operations
│   ├── auth.py           # Authentication (login, session validation)
│   ├── config.py         # Database configuration
│   ├── schema.sql        # Database schema
│   ├── qr_utils.py       # QR code generation utilities
│   └── excel_utils.py    # Excel import + generic export utilities
│
└── logs/                 # Application logs (gitignored)
```

---

## 10. ENVIRONMENT VARIABLES

```env
# Database
DB_HOST=xxx.railway.app
DB_PORT=3306
DB_NAME=asset_management
DB_USER=xxx
DB_PASSWORD=xxx

# App Settings
DATA_SOURCE=mysql
LOG_DIR=logs

# Email Notifications (Gmail SMTP)
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Legacy (Airtable - no longer used)
AIRTABLE_API_KEY=xxx
AIRTABLE_BASE_ID=xxx
```

---

## 11. DEPLOYMENT

### Current Setup
- **Platform:** Railway
- **Auto-Deploy:** Yes (on push to `main` branch)
- **URL:** [Your Railway URL]

### Deployment Flow
```
Local Development
       │
       ▼
   git commit
       │
       ▼
   git push origin main
       │
       ▼
   Railway detects push
       │
       ▼
   Auto-builds & deploys
       │
       ▼
   Live in ~2 minutes
```

---

## 12. KNOWN ISSUES & LIMITATIONS

### Streamlit Limitations
1. **No Real-time Updates:** Page must refresh to see changes from other users
2. **Session State:** Lost on full page refresh (mitigated with `st.query_params` token persistence)
3. **Custom JavaScript:** `st.markdown()` blocks `<script>` tags; `components.html()` runs in sandboxed iframe
4. **HTML Not Clickable:** Cannot make HTML elements trigger Python callbacks - only Streamlit widgets can

### Current Workarounds
1. **KPI Card Navigation:** Uses merged card+button design (button styled as card footer)
2. **Chart Clicks:** Uses `streamlit_plotly_events` for click detection
3. **Session Validation:** Cached for 5 minutes to prevent login flicker
4. **Anchor Tags Avoided:** All navigation uses `st.button()` to preserve session state
5. **Session Persistence:** Token stored in `st.query_params["sid"]` to survive hard refresh
6. **Anti-Flicker:** `.stApp { opacity: 0 }` hides entire app until auth resolves; login/dashboard CSS sets `opacity: 1`
7. **Login Page Full-Width:** `section.main { width: 100%; margin-left: 0 }` overrides Streamlit's sidebar margin on login page
8. **query_params Pattern:** `login_user()`/`logout_user()` only handle session state. Callers set/clear `st.query_params` directly (never inside silent `try/except`)

### Technical Debt
1. `app.py` is ~230 lines — modular extraction complete (Steps 1-8)
2. No automated tests
3. No staging environment
4. Existing DB functions (pre-column-mapping) lack `finally` blocks for connection cleanup — only affects error paths

### Resolved Issues (Feb 16, 2026)
1. ~~Production crash: `width="stretch"` incompatible with Streamlit 1.31.0~~ → Reverted all 53 occurrences back to `use_container_width=True` (`525353a`, `b9b9e38`)

### Resolved Issues (Feb 11, 2026)
1. ~~Login page flash on refresh~~ → Fixed with `.stApp { opacity: 0 }` anti-flicker (replaces fadeIn animation)
2. ~~Sidebar missing after login~~ → Anti-flicker CSS had `width: 0` on sidebar never overridden; simplified to `display: none` only
3. ~~Login page compressed after logout~~ → Added `section.main { margin-left: 0 }` to override Streamlit's inline sidebar margin
4. ~~Session lost on transient network errors~~ → Split exception handling: only clear sid on explicit auth failure, keep sid on network errors
5. ~~Session token not in URL on production~~ → `st.query_params` inside `try/except Exception: pass` failed silently on Railway; moved to handler
6. ~~Login page compressed after logout (production only)~~ → Same silent `st.query_params` pattern in `logout_user()`; moved to sign out handler
7. ~~KeyError: None on logout~~ → `st.query_params.clear()` doesn't stop script execution; added `safe_rerun()` after

### Resolved Issues (Feb 10, 2026)
1. ~~Login lost on hard refresh (production)~~ → Fixed with `st.query_params` session token persistence
2. ~~Sidebar hidden after login (production)~~ → Fixed with `initial_sidebar_state="expanded"`
3. ~~Login page layout shift~~ → Fixed with CSS fadeIn animation + logo space reservation
4. ~~Duplicate clients in Select Client dropdown~~ → Fixed with `.unique()` + DB cleanup
5. ~~"With_Client" shown as client name in charts~~ → Fixed with DB location data correction
6. ~~Localhost and production data out of sync~~ → Synced localhost from production

### Resolved Issues (Feb 6, 2026)
1. ~~Login loop when clicking dashboard cards~~ → Fixed with Streamlit buttons
2. ~~Invisible text area borders~~ → Fixed with darker border color
3. ~~Disconnected card+button appearance~~ → Fixed with merged design
4. ~~Bulk selection clear error~~ → Fixed with callback + flag pattern

---

## 13. DEVELOPMENT HISTORY

### Major Milestones
| Date | Milestone |
|------|-----------|
| Jan 2026 | Initial development with Airtable |
| Jan 2026 | Added authentication system |
| Jan 2026 | Migrated from Airtable to MySQL |
| Feb 2026 | Added bulk operations |
| Feb 2026 | Implemented clickable dashboard metrics |
| Feb 2026 | Fixed navigation issues |
| Feb 6, 2026 | Fixed login loop issue |
| Feb 6, 2026 | Implemented merged card+button design |
| Feb 10, 2026 | Assets page enhancements (search form, badges, quick actions) |
| Feb 10, 2026 | Pagination navigation on all tables |
| Feb 10, 2026 | Session persistence on hard refresh |
| Feb 10, 2026 | Data quality fixes (duplicate clients, asset locations) |
| Feb 10, 2026 | Retired Assets KPI cards (Sold, Disposed) |
| Feb 10, 2026 | Localhost synced from production database |
| Feb 11, 2026 | Anti-flicker CSS overhaul (opacity:0 approach) |
| Feb 11, 2026 | Session restore optimization (from_restore flag) |
| Feb 11, 2026 | Login page full-width fix after logout |
| Feb 11, 2026 | Fix session token not persisting on production |
| Feb 11, 2026 | Fix compressed login page after logout on production |
| Feb 12, 2026 | Extract modular architecture from app.py (Steps 1-8) |
| Feb 12, 2026 | Fix Activity Log rendering raw HTML as code blocks |
| Feb 12, 2026 | Fix Streamlit deprecation + pandas SQLAlchemy warnings (P0) |
| Feb 12, 2026 | Asset History Timeline — unified chronological view (P1) |
| Feb 16, 2026 | Production hotfix: revert `width="stretch"` → `use_container_width=True` (53 occurrences) |
| Feb 16, 2026 | Dashboard date range filters with presets + Period Activity section |
| Feb 16, 2026 | Export to Excel on all data pages (generic utility + formatted headers) |
| Feb 23, 2026 | Streamlit upgrade 1.31.0 → 1.53.1 (eliminates version mismatch) |
| Feb 23, 2026 | SLA email notifications (Gmail SMTP, manual trigger, HTML reports) |
| Feb 23, 2026 | Column mapping import (upload any Excel, auto-suggest, saved profiles) |

### Recent Changes (February 23, 2026)

#### Streamlit Upgrade (`78abb20`)
- Upgraded `requirements.txt` from `streamlit==1.31.0` → `streamlit==1.53.1`
- Eliminates 22-version gap between local dev and production
- Resolves `width="stretch"` incompatibility (production now supports modern Streamlit APIs)

#### SLA Email Notifications (`78abb20`)
- New `services/email_service.py` — Gmail SMTP sender with HTML report builder
- Manual "Email SLA Report" button on Dashboard (Admin/Operations roles only)
- HTML email includes: summary bar (Critical/Warning/OK counts), asset table with color-coded badges, SLA thresholds reference
- Sends to all active Admin + Operations users with email addresses
- Requires `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` env vars (Gmail App Password)
- Button shows disabled state if email not configured
- Added `EMAIL_CONFIG` to `config/constants.py`, `get_sla_breached_assets()` to `services/sla_service.py`

#### Column Mapping Import (`78abb20`)
- Redesigned Import tab with 5-step flow: Upload → Map Columns → Preview → Validate → Import
- Upload any Excel file (vendor invoices, procurement sheets, old IT registers)
- Auto-suggest column mapping using keyword matching (18 app fields with multiple keywords each)
- Save/load/delete reusable mapping profiles (stored in `import_mapping_profiles` MySQL table)
- Serial Number highlighted as required field
- Duplicate field protection (auto-suggest tracks used fields, apply_column_mapping deduplicates)
- Connection pool leak fix: all 3 new DB functions use `try/finally` for guaranteed `conn.close()`
- Backward compatible: template upload auto-maps all columns correctly
- New functions: `detect_columns()`, `auto_suggest_mapping()`, `apply_column_mapping()` in `database/excel_utils.py`
- New DB functions: `get_import_profiles()`, `save_import_profile()`, `delete_import_profile()` in `database/db.py`
- Files changed: `database/db.py`, `database/excel_utils.py`, `views/import_export.py`, `config/constants.py`, `services/sla_service.py`, `views/dashboard.py`, `services/email_service.py` (new), `requirements.txt`

### Previous Changes (February 16, 2026)

#### Production Hotfix: `width="stretch"` Incompatibility (`525353a`, `b9b9e38`)
- **Problem:** P0 fix replaced `use_container_width=True` → `width="stretch"` across 53 calls, but production runs Streamlit 1.31.0 which doesn't support `width` param on any widget
- **Root Cause:** Local dev runs Streamlit 1.53.1 (22-version gap). Local testing passed but production crashed on login and dashboard
- **Solution:** Reverted all 53 occurrences back to `use_container_width=True`. First hotfix (`525353a`) covered 3 `form_submit_button` calls; full fix (`b9b9e38`) reverted remaining 50 across 9 files
- **Lesson:** Always verify API compatibility against `requirements.txt` pinned version, not local installed version

#### Dashboard Date Range Filters (`de2511f`)
- Added date range selector UI after Refresh button with preset options (This Week, This Month, Last Month, Last 30 Days, Last 90 Days, Custom)
- Added Period Activity section showing time-filtered counts: New Assets, Assignments, Returns, Issues, Repairs
- Existing KPI cards remain unchanged (point-in-time status counts)
- Helper functions: `_get_date_presets()`, `_count_in_range(df, date_col, start, end)`
- Files changed: `views/dashboard.py` only

#### Export to Excel — All Data Pages (`de2511f`)
- Added generic `export_dataframe_to_excel(df, sheet_name)` to `database/excel_utils.py`
- Formatted Excel: orange headers (#F97316), auto-width columns, frozen header row, borders
- Side-by-side Excel + CSV download buttons on: Assets, Assignments, Issues, Repairs, Reports (3 tabs), Billing
- Files changed: `database/excel_utils.py`, `views/assets.py`, `views/billing.py`, `views/reports.py`, `views/assignments.py`, `views/issues_repairs.py`

### Previous Changes (February 12, 2026)

#### Modular Architecture Extraction (Steps 1-8)
- **Problem:** `app.py` was 11,529 lines — a monolith containing all config, utilities, business logic, and UI code
- **Solution:** Extracted in 8 steps into 5 module layers:
  - **Steps 1-5** (`config/`, `core/`, `services/`): constants, CSS, RBAC, error handling, data fetching, billing/audit/asset/SLA business logic (9 modules)
  - **Step 6** (`components/`): reusable UI components — charts, empty states, feedback badges, confirmation dialogs (4 modules)
  - **Step 7** (`views/`): 13 page renderers with AppContext dispatch pattern (15 modules)
  - **Step 8** (`core/auth.py`, `core/navigation.py`): auth session management, login page, sidebar navigation, footer (2 modules)
- **Result:** app.py reduced from 11,529 → ~230 lines (98% reduction)
- **Key commits:** `73144f5` (Steps 1-5), `0ca8d4f` (Step 6), `6cb802b` (Step 7), `4556bea` (Step 8)
- **AppContext pattern:** Each page module exports `render(ctx: AppContext)`. AppContext bundles shared state (DataFrames, flags). `PAGE_REGISTRY` dict maps page names to render functions.
- **Named `views/` not `pages/`:** Streamlit auto-detects a `pages/` directory as multipage nav — renamed to avoid collision with our custom sidebar navigation.
- **No logic changes** — all code moved exactly as-is, only imports updated
- **Extraction complete** — app.py is now pure orchestration (logging, page config, auth flow, data loading, dispatch)

#### Activity Log HTML Rendering Fix
- **Problem:** Activity Log page showed raw HTML tags as text instead of rendering them
- **Root Cause:** Indented triple-quoted f-strings had 4+ leading spaces, which Markdown treats as code blocks
- **Solution:** Replaced with string concatenation (zero indentation) — `commit 1748e18`

#### P0: Fix Deprecation Warnings (`d7ec010`) — ⚠️ Partially Reverted
- Replaced `use_container_width=True` → `width="stretch"` across 10 files (53 replacements)
- **REVERTED:** `width="stretch"` back to `use_container_width=True` — production Streamlit 1.31.0 doesn't support `width` param (`525353a`, `b9b9e38`)
- Added `_query_to_df()` cursor-based helper in `database/db.py`, replaced all 8 `pd.read_sql()` calls ← this part remains
- Streamlit deprecation warnings will persist until production Streamlit is upgraded

#### P1: Asset History Timeline (`22d467a`)
- Replaced basic "View Asset History" expander with unified chronological timeline
- Merges 4 data sources: assignments (blue), issues (red), repairs (orange), activity log (gray)
- Color-coded cards with left border, event limit selector (50/100/200), summary count bar
- Files changed: `views/assets.py` only (2 helper functions + expander replacement)

### Previous Changes (February 11, 2026)

#### Anti-Flicker CSS Overhaul
- **Problem:** Login page flashed briefly on refresh; page appeared compressed
- **Root Cause:** Old fadeIn animation was insufficient; sidebar CSS overrides conflicted
- **Solution:** Hide entire `.stApp` with `opacity: 0` until auth resolves. Login CSS and dashboard CSS each set `opacity: 1` to reveal the correct page.
- Anti-flicker sidebar CSS simplified to `display: none` only (no width/min-width overrides that could conflict with dashboard CSS)

#### Session Restore Optimization
- **Problem:** `login_user()` re-set `st.query_params["sid"]` during session restore, potentially triggering unnecessary Streamlit rerun
- **Solution:** Removed `st.query_params` from `login_user()` entirely. Callers handle query params directly.

#### Exception Handling Improvement
- **Problem:** Catch-all `except (ValueError, Exception)` deleted sid from URL on any error, including transient network/DB failures
- **Solution:** Split into `except ValueError` (malformed sid → clear) and `except Exception` (network error → keep sid for retry on next load). Session restore uses `_clear_sid` flag to call `st.query_params.clear()` OUTSIDE the try/except.

#### Login Page Compressed After Logout
- **Problem:** After logout, login page appeared compressed because Streamlit's inline margin for the expanded sidebar was still applied to `.main`
- **Solution:** Added `section.main { width: 100% !important; margin-left: 0 !important; }` to login page CSS. Broadened to also override `[data-testid="stMain"]` and `.stMainBlockContainer`.

#### Session Token Not Persisting on Production
- **Problem:** After login on production, `?sid=` was NOT appearing in the URL. Worked on localhost.
- **Root Cause:** `st.query_params["sid"] = value` inside `login_user()` was wrapped in `try/except Exception: pass` which silently caught a production-specific error (Railway reverse proxy)
- **Solution:** Moved `st.query_params` out of `login_user()`. Login form handler sets it directly. Removed silent `try/except`. Added logging.

#### Compressed Login Page After Logout (Production Only)
- **Problem:** Login page compressed ONLY on production after logout, not on localhost
- **Root Cause:** Same `try/except Exception: pass` pattern in `logout_user()`. `del st.query_params["sid"]` failed silently → stale `?sid=` → session restore code ran with failed query param ops → inconsistent render state
- **Solution:** Removed `st.query_params` from `logout_user()`. Sign out button calls `st.query_params.clear()` directly, then `safe_rerun()`.

#### Key Pattern: `st.query_params` on Production
- `login_user()` and `logout_user()` now ONLY handle session state and DB operations
- Callers (`login form handler`, `sign out button`) handle `st.query_params` directly
- NEVER wrap `st.query_params` in silent `try/except Exception: pass`
- `st.query_params.clear()` does NOT stop script execution — always follow with `safe_rerun()`

### Previous Changes (February 10, 2026)

#### Session Persistence on Hard Refresh
- **Problem:** Production hard refresh lost login session
- **Root Cause:** Streamlit session state is in-memory, tied to WebSocket
- **Solution:** Persist session token in `st.query_params["sid"]`, restore on page load via `validate_session()`

#### Sidebar Visibility Fix
- **Problem:** Sidebar hidden after login on production
- **Solution:** Changed `initial_sidebar_state` from `"collapsed"` to `"expanded"`

#### Assets Page Enhancements (6 changes)
1. Orange Search button + ghost Clear Filters (wrapped in `st.form`)
2. Summary status badges below header
3. Active filter indicator pills
4. Table column reorder (Serial, Brand, Model, Status, Location first)
5. Export CSV moved to top-right
6. Per-row quick actions panel

#### Pagination Navigation
- Added page number buttons (1, 2, 3...) below all 6 tables
- Active page highlighted orange, centered layout with "Page X of Y"

#### Data Quality Fixes
- Removed 6 duplicate client records from production DB
- Fixed 4 assets with `current_location = 'With_Client'` → `'X3i Solution'`
- Fixed client dropdown deduplication (`.unique()`)
- Synced localhost database from production

#### Retired Assets KPI Cards
- New "RETIRED ASSETS" section on Dashboard
- Sold (purple #8b5cf6) and Disposed (gray #6b7280) cards
- Clickable → navigates to Assets page filtered by status

### Previous Changes (February 6, 2026)

#### Login Loop Fix
- **Problem:** Clicking any dashboard card caused redirect to login page in infinite loop
- **Root Cause:** Anchor tags (`<a href="?nav=...">`) caused full page reload, losing Streamlit session state
- **Solution:** Replaced all anchor tags with Streamlit buttons (`st.button()`)
- Added safety check after session validation to prevent redirect loops
- Removed query parameter navigation code

#### Dashboard Card UX Improvement
- **Problem:** KPI cards had small "View" buttons below them that looked disconnected
- **Approaches Tried:**
  1. CSS overlay with `:has()` selector - Failed (browser compatibility)
  2. JavaScript click forwarding via `components.html()` - Failed (iframe sandboxing)
- **Final Solution (Option B):** Merged card+button design
  - Cards have bottom border-radius removed (connects to button)
  - Buttons styled as card footer with rounded bottom corners
  - Combined hover effect - card and button lift together
  - Seamless single-element appearance

#### Notes Text Area Border Fix
- **Problem:** Notes field in Add Asset page had invisible border
- **Solution:** Changed border color from `#e2e8f0` to `#cbd5e1` (darker, more visible)
- Added multiple CSS selectors for reliable targeting

#### Bulk Selection Clear Error Fix
- **Problem:** Clicking "Clear Selection" in Assets bulk operations caused `StreamlitAPIException`
- **Root Cause:** Cannot modify `st.session_state.bulk_asset_select` after multiselect widget is instantiated
- **Solution:** Implemented callback + flag pattern
  - Added `clear_bulk_selection_flag` session state variable
  - Clear Selection button uses `on_click` callback to set flag
  - Flag is checked BEFORE multiselect widget renders
  - Selection cleared and flag reset before widget instantiation

---

## 14. CONTACTS & OWNERSHIP

| Role | Responsibility |
|------|----------------|
| **Product Owner** | Feature decisions, priorities |
| **Developer** | Implementation, bug fixes |
| **Users** | Operations team (5+ people) |

---

## 15. QUICK REFERENCE

### How to Run Locally
```bash
cd AssetManagementApp
pip install -r requirements.txt
streamlit run app.py
```

### How to Deploy
```bash
git add .
git commit -m "Description of changes"
git push origin main
# Railway auto-deploys
```

### How to Check Logs
```bash
# Railway dashboard > Your project > Logs
```

### Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| Login page flashes | Session validation is cached, wait 5 min or clear cache |
| Changes not appearing | Hard refresh (Ctrl+Shift+R) |
| Navigation not working | Check if using `window.parent.location` |
| Database connection error | Check Railway MySQL status |

---

*This document should be updated whenever significant changes are made to the system.*
