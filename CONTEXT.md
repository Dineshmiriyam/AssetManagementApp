# NXTBY Asset Management System - Project Context

> **Last Updated:** February 2026
> **Version:** 1.0
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
streamlit==1.31.0
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
│                      (app.py)                                │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │  Dashboard  │   Assets    │   Clients   │   Billing   │  │
│  ├─────────────┼─────────────┼─────────────┼─────────────┤  │
│  │ Quick Acts  │ Assignments │   Issues    │  Settings   │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MySQL DATABASE                            │
│                     (Railway)                                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  assets  │  clients │  users   │ activity │assignments│  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

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
- [x] KPI cards clickable - navigate to filtered Assets page
- [x] SLA indicators (Critical, Warning, OK)
- [x] Revenue metrics (Admin/Finance only)
- [x] Interactive charts (click to filter)
- [x] Quick action buttons

### Assets Page
- [x] View all assets with filters
- [x] Search by serial number, brand, model
- [x] Filter by status, brand, type, location
- [x] Bulk operations (select multiple, change status, assign)
- [x] Individual asset actions (Fix, Send to Vendor)
- [x] SLA filter integration
- [x] Linked record navigation

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
- [x] Excel import
- [x] Session management
- [x] Login/logout with activity logging

---

## 7. PLANNED FEATURES (Priority Order)

### High Priority
- [ ] Asset history timeline (view all changes to an asset)
- [ ] Export to Excel (filtered data)
- [ ] Email notifications (SLA alerts)
- [ ] Dashboard date range filters

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

---

## 9. FILE STRUCTURE

```
AssetManagementApp/
├── app.py                 # Main application (all UI + logic)
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (DO NOT COMMIT)
├── .gitignore
├── CONTEXT.md            # This file
├── GUARDRAILS.md         # Development rules
├── DEPLOYMENT.md         # Deployment checklist
├── README.md
│
├── database/
│   ├── schema.sql        # Database schema
│   ├── qr_utils.py       # QR code generation utilities
│   └── migrations/       # Database migrations
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
1. **Iframe Environment:** Streamlit runs in iframe, requires `window.parent.location` for navigation
2. **No Real-time Updates:** Page must refresh to see changes from other users
3. **Session State:** Lost on page refresh (mitigated with session caching)
4. **Custom Components:** Limited ability to add custom JavaScript

### Current Workarounds
1. **KPI Card Navigation:** Uses URL query parameters instead of hidden buttons
2. **Chart Clicks:** Uses `streamlit_plotly_events` for click detection
3. **Session Validation:** Cached for 5 minutes to prevent login flicker

### Technical Debt
1. `app.py` is large (~10,000 lines) - could be split into modules
2. Some CSS is duplicated
3. No automated tests

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

### Recent Changes
- Removed visible button boxes below KPI cards
- Fixed KPI card click navigation (window.parent.location)
- Added multiselect dropdown border
- Enhanced sidebar navigation

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
