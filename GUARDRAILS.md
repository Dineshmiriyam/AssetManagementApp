# Development Guardrails

> **Purpose:** Rules to prevent common mistakes and ensure smooth development
> **Audience:** Anyone working on this codebase (developers, AI assistants)

---

## 🚫 NEVER DO

### Code Changes
| Rule | Reason |
|------|--------|
| **Never change UI design unless explicitly asked** | User has specific design preferences |
| **Never add features while fixing bugs** | Scope creep causes confusion |
| **Never remove code without understanding its purpose** | May break dependent features |
| **Never hardcode credentials** | Security risk |
| **Never use `st.experimental_*` in production** | May be deprecated |

### Git & Deployment
| Rule | Reason |
|------|--------|
| **Never push to `main` without testing locally** | Breaks production |
| **Never force push (`git push -f`)** | Loses history |
| **Never commit `.env` file** | Contains secrets |
| **Never deploy on Fridays** | No one wants weekend emergencies |

### Database
| Rule | Reason |
|------|--------|
| **Never DELETE without WHERE clause** | Data loss |
| **Never run migrations without backup** | Data loss |
| **Never store passwords in plain text** | Security |

---

## ✅ ALWAYS DO

### Before Making Changes
| Action | How |
|--------|-----|
| **Read the file before editing** | Use Read tool first |
| **Understand the context** | Check CONTEXT.md |
| **Confirm scope** | "You want me to change X only, correct?" |
| **Check git status** | Ensure clean working directory |

### When Making Changes
| Action | How |
|--------|-----|
| **Make minimal changes** | Only what's requested |
| **Preserve existing style** | Match surrounding code |
| **Test locally first** | `streamlit run app.py` |
| **Comment complex logic** | Future you will thank you |

### After Making Changes
| Action | How |
|--------|-----|
| **Verify syntax** | `python -m py_compile app.py` |
| **Commit with clear message** | Describe what and why |
| **Push to GitHub** | `git push origin main` |
| **Confirm deployment** | Check Railway dashboard |
| **Tell user to hard refresh** | Ctrl+Shift+R |

---

## 📋 CHANGE REQUEST TEMPLATE

When requesting changes, use this format:

```
## What I Want
[Clear description of the desired outcome]

## Where
[Page/section/component name]

## Current Behavior
[What happens now]

## Expected Behavior
[What should happen]

## Don't Change
[Explicitly list what should NOT be modified]

## Screenshot
[If applicable, attach image with annotations]
```

### Example:
```
## What I Want
Make KPI cards clickable to navigate to Assets page

## Where
Dashboard page > Inventory Overview section > KPI cards

## Current Behavior
Clicking KPI card does nothing

## Expected Behavior
Clicking "Deployed" card → Assets page filtered by WITH_CLIENT status

## Don't Change
- Card design/colors
- Card layout
- Any other section

## Screenshot
[Image showing the 5 KPI cards]
```

---

## 🔧 RESPONSE TEMPLATE (For AI/Developers)

When confirming changes:

```
## Understood
[Restate the request in your own words]

## Approach
[Explain how you'll implement it]

## Files to Modify
- `app.py` lines XXX-YYY

## Will Change
- [Specific change 1]
- [Specific change 2]

## Won't Change
- [Confirm what stays the same]

## How to Test
[Steps to verify the fix]
```

---

## 🎨 UI/UX GUIDELINES

### Design Principles
1. **Consistency** - Same patterns everywhere
2. **Simplicity** - Remove unnecessary elements
3. **Feedback** - User knows what's happening
4. **Accessibility** - Readable colors, clear labels

### Color Palette (Reference)
| Purpose | Color | Hex |
|---------|-------|-----|
| Primary | Orange | #f97316 |
| Success | Green | #10b981 |
| Warning | Amber | #f59e0b |
| Error | Red | #ef4444 |
| Info | Blue | #3b82f6 |
| Neutral | Gray | #6b7280 |

### Component Patterns
- **Cards:** 12px border-radius, subtle shadow
- **Buttons:** Consistent padding, clear labels
- **Tables:** Alternating row colors, hover states
- **Forms:** Labels above inputs, clear validation

---

## 🚀 DEPLOYMENT CHECKLIST

Before every deployment:

```
□ 1. Test locally (`streamlit run app.py`)
□ 2. Check for Python errors (`python -m py_compile app.py`)
□ 3. Review changes (`git diff`)
□ 4. Commit with clear message (`git commit -m "..."`)
□ 5. Push to GitHub (`git push origin main`)
□ 6. Check Railway deployment status
□ 7. Hard refresh browser (Ctrl+Shift+R)
□ 8. Test the specific feature changed
□ 9. Check no other features broke
```

---

## 🐛 DEBUGGING CHECKLIST

When something doesn't work:

```
□ 1. Check browser console (F12 > Console)
□ 2. Check Railway logs
□ 3. Verify code was committed (`git status`)
□ 4. Verify code was pushed (`git log origin/main`)
□ 5. Hard refresh browser (Ctrl+Shift+R)
□ 6. Clear browser cache if needed
□ 7. Check if it's a Streamlit iframe issue (use window.parent)
□ 8. Test in incognito mode
```

---

## 📁 FILE ORGANIZATION

### Where to Put Things

| Type | Location |
|------|----------|
| All UI code | `app.py` |
| Database utilities | `database/` folder |
| QR code functions | `database/qr_utils.py` |
| Documentation | Root folder (`.md` files) |
| Environment vars | `.env` (never commit) |

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `get_all_assets()` |
| Variables | snake_case | `asset_count` |
| Constants | UPPER_SNAKE | `ASSET_STATUSES` |
| CSS classes | kebab-case | `kpi-card-title` |
| Session state keys | snake_case | `current_page` |

---

## ⚠️ KNOWN GOTCHAS

### Streamlit-Specific

1. **Session State Resets**
   - Happens on page refresh
   - Solution: Use `st.session_state` with defaults

2. **Iframe Navigation**
   - `window.location` doesn't work
   - Solution: Use `window.parent.location`

3. **CSS Specificity**
   - Streamlit's CSS may override yours
   - Solution: Use `!important` when needed

4. **Component Keys**
   - Must be unique across entire app
   - Solution: Include context in key name (`assets_search`, `billing_search`)

5. **Rerun Behavior**
   - `st.rerun()` restarts entire script
   - Solution: Set session state BEFORE calling rerun

### Database-Specific

1. **Connection Timeouts**
   - Railway MySQL may timeout
   - Solution: Reconnect on error

2. **Datetime Handling**
   - MySQL returns datetime, Streamlit needs string
   - Solution: Convert with `.strftime()` or `pd.to_datetime()`

---

## 📞 ESCALATION PATH

When stuck:

1. **Check CONTEXT.md** - Might have the answer
2. **Check this file** - Common issues documented
3. **Search the codebase** - Similar pattern might exist
4. **Ask with full context** - Include error message, what you tried

---

*Last updated: February 2026*
