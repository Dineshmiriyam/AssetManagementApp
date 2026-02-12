"""
CSS styles for Asset Lifecycle Management System.
Extracted from app.py — pure string data, no runtime dependencies.
"""


def get_anti_flicker_css():
    """CSS that hides all UI until auth is resolved. Runs first to prevent flash."""
    return """
<style>
/* Hide entire app until auth decision (login CSS or dashboard CSS reveals it) */
.stApp { opacity: 0 !important; }

/* Hide sidebar until auth decision */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
section[data-testid="stSidebar"] {
    display: none !important;
}
</style>
"""


def get_login_css():
    """Login page CSS matching mis.nxtby.com reference design."""
    return """
    <style>
    /* Hide Streamlit defaults AND sidebar for login page */
    #MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], section[data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* Reveal app on login page */
    .stApp {
        opacity: 1 !important;
        background: #f5f5f5 !important;
        min-height: 100vh;
    }

    /* Ensure main content is full width on login (override ALL sidebar margins) */
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
        width: 100% !important;
        min-width: 100% !important;
    }
    section.main {
        width: 100% !important;
        min-width: 100% !important;
        margin-left: 0 !important;
    }
    .main .block-container,
    .stMainBlockContainer {
        max-width: 100% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* ============ BRAND SECTION (Above Card) ============ */
    .login-brand {
        text-align: center;
        margin-bottom: 1.25rem;
        min-height: 80px; /* Reserve space for logo + tagline to prevent layout shift */
    }

    .login-brand-logo-img {
        height: 48px;
        width: auto;
        margin-bottom: 0.5rem;
        display: block;
        margin-left: auto;
        margin-right: auto;
    }

    .login-brand-tagline {
        color: #6b7280;
        font-size: 0.875rem;
        margin: 0;
    }

    /* ============ WHITE CARD - Single unified card ============ */
    /* Header is just text inside the form, not separate */
    .login-card-header {
        text-align: center;
        padding: 0 0 1.25rem 0;
        margin: 0;
        background: transparent;
    }

    .login-card-header h2 {
        color: #111827;
        font-size: 1.125rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 0.05em;
    }

    /* Form IS the white card */
    [data-testid="stForm"] {
        background: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 2rem !important;
        margin-left: auto !important;
        margin-right: auto !important;
        max-width: 380px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1) !important;
    }

    /* Hide "Press Enter to submit form" hint */
    [data-testid="InputInstructions"],
    div[data-testid="InputInstructions"],
    .stTextInput [data-testid="InputInstructions"],
    [data-testid="stForm"] [data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
    }

    /* Input Fields - Full rectangular border like reference */
    .stTextInput {
        margin-bottom: 1.25rem !important;
    }

    .stTextInput > label {
        color: #374151 !important;
        font-size: 0.875rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
    }

    /* Input container - FULL BORDER */
    .stTextInput > div > div,
    .stTextInput [data-baseweb="base-input"],
    .stTextInput [data-baseweb="input"] {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-top: 1px solid #d1d5db !important;
        border-right: 1px solid #d1d5db !important;
        border-bottom: 1px solid #d1d5db !important;
        border-left: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        box-shadow: none !important;
        outline: none !important;
    }

    .stTextInput > div > div:hover,
    .stTextInput [data-baseweb="base-input"]:hover {
        border: 1px solid #9ca3af !important;
        border-color: #9ca3af !important;
    }

    .stTextInput > div > div:focus-within,
    .stTextInput [data-baseweb="base-input"]:focus-within {
        border: 1px solid #f97316 !important;
        border-color: #f97316 !important;
        box-shadow: none !important;
    }

    /* Input element */
    .stTextInput input {
        color: #111827 !important;
        font-size: 0.95rem !important;
        padding: 0.75rem 1rem !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }

    .stTextInput input::placeholder {
        color: #9ca3af !important;
    }

    /* Password eye button - seamless with input */
    .stTextInput button,
    .stTextInput [data-testid="passwordShowButton"],
    .stTextInput [data-testid="baseButton-secondary"] {
        color: #6b7280 !important;
        border: none !important;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0.5rem !important;
        margin: 0 !important;
    }

    .stTextInput button:hover {
        color: #f97316 !important;
        background: transparent !important;
    }

    .stTextInput button:focus {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Remove any background from button container */
    .stTextInput > div > div > div:last-child,
    .stTextInput [data-baseweb="input"] > div:last-child {
        background: transparent !important;
        border: none !important;
    }

    /* Submit Button - Orange like nxtby.com */
    .stFormSubmitButton > button,
    .stFormSubmitButton > button:focus,
    .stFormSubmitButton > button:active,
    [data-testid="stForm"] .stFormSubmitButton > button,
    [data-testid="stFormSubmitButton"] > button {
        background: #f97316 !important;
        background-color: #f97316 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.875rem 1.5rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        margin-top: 1rem !important;
        box-shadow: none !important;
    }

    .stFormSubmitButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background: #ea580c !important;
        background-color: #ea580c !important;
    }

    .stFormSubmitButton > button:disabled {
        background: #d1d5db !important;
        background-color: #d1d5db !important;
    }

    /* Alerts */
    .stAlert {
        background: #fef2f2 !important;
        border: 1px solid #fecaca !important;
        border-radius: 6px !important;
        margin-top: 0.75rem !important;
    }

    .stAlert p {
        color: #dc2626 !important;
        font-size: 0.85rem !important;
    }

    .session-warning {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 6px;
        padding: 0.625rem 1rem;
        margin-bottom: 1rem;
        text-align: center;
    }

    .session-warning p {
        color: #b45309;
        font-size: 0.85rem;
        margin: 0;
    }

    .service-unavailable {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
    }

    .service-unavailable p {
        color: #dc2626;
        font-size: 0.85rem;
        margin: 0;
    }

    /* Responsive */
    @media (max-width: 480px) {
        .login-card-header {
            max-width: 100%;
            border-radius: 0;
            margin: 0;
        }
        [data-testid="stForm"] {
            max-width: 100% !important;
            border-radius: 0 !important;
            margin: 0 !important;
        }
    }
    </style>
"""


def get_dashboard_css():
    """Full design system CSS for authenticated dashboard."""
    return """
<style>
    /* ==========================================================================
       AUTHENTICATED USER: Reveal app and show sidebar
       ========================================================================== */
    .stApp { opacity: 1 !important; }

    [data-testid="stSidebar"],
    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
    }

    /* ==========================================================================
       DESIGN SYSTEM - Enterprise Asset Management Dashboard
       Version: 2.0

       This design system provides consistent tokens for colors, typography,
       spacing, and motion across the entire application.
       ========================================================================== */

    :root {
        /* ------------------------------------------------------------------
           1. COLOR TOKENS
           ------------------------------------------------------------------ */

        /* Neutral Background Scale (Light → Dark) */
        --color-bg-primary: #ffffff;           /* Main content background */
        --color-bg-secondary: #f8fafc;         /* Cards, elevated surfaces */
        --color-bg-tertiary: #f1f5f9;          /* Subtle backgrounds, hover states */
        --color-bg-muted: #e2e8f0;             /* Borders, dividers */

        /* Neutral Background Scale (Dark - Sidebar) */
        --color-sidebar-bg: #1a2332;           /* Sidebar primary */
        --color-sidebar-hover: #232f42;        /* Sidebar hover state */
        --color-sidebar-active: rgba(249, 115, 22, 0.15);  /* Active nav item */
        --color-sidebar-border: #2d3748;       /* Sidebar dividers */

        /* Text Colors */
        --color-text-primary: #1e293b;         /* Headings, primary text */
        --color-text-secondary: #475569;       /* Body text, labels */
        --color-text-tertiary: #64748b;        /* Captions, metadata */
        --color-text-muted: #94a3b8;           /* Placeholders, disabled */
        --color-text-inverse: #ffffff;         /* Text on dark backgrounds */

        /* Brand / Accent */
        --color-brand-primary: #f97316;        /* Primary orange */
        --color-brand-hover: #ea580c;          /* Orange hover */
        --color-brand-light: rgba(249, 115, 22, 0.1);  /* Orange tint */

        /* Semantic Colors - Success */
        --color-success: #22c55e;
        --color-success-dark: #16a34a;
        --color-success-light: #dcfce7;
        --color-success-bg: #f0fdf4;

        /* Semantic Colors - Warning */
        --color-warning: #f59e0b;
        --color-warning-dark: #d97706;
        --color-warning-light: #fef3c7;
        --color-warning-bg: #fffbeb;

        /* Semantic Colors - Critical / Error */
        --color-critical: #ef4444;
        --color-critical-dark: #dc2626;
        --color-critical-light: #fee2e2;
        --color-critical-bg: #fef2f2;

        /* Semantic Colors - Info / Active */
        --color-info: #3b82f6;
        --color-info-dark: #2563eb;
        --color-info-light: #dbeafe;
        --color-info-bg: #eff6ff;

        /* Semantic Colors - Neutral (for non-semantic states) */
        --color-neutral: #64748b;
        --color-neutral-dark: #475569;
        --color-neutral-light: #e2e8f0;
        --color-neutral-bg: #f8fafc;

        /* Data Visualization Colors (Muted, accessible palette) */
        --color-data-1: #6366f1;              /* Indigo */
        --color-data-2: #8b5cf6;              /* Violet */
        --color-data-3: #ec4899;              /* Pink */
        --color-data-4: #f97316;              /* Orange (brand) */
        --color-data-5: #14b8a6;              /* Teal */
        --color-data-6: #64748b;              /* Slate */

        /* Border Colors */
        --color-border-light: #e2e8f0;
        --color-border-default: #cbd5e1;
        --color-border-dark: #94a3b8;

        /* Shadow Colors */
        --shadow-color: rgba(15, 23, 42, 0.08);
        --shadow-color-heavy: rgba(15, 23, 42, 0.12);

        /* ------------------------------------------------------------------
           2. TYPOGRAPHY
           ------------------------------------------------------------------ */

        /* Font Family */
        --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        --font-family-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;

        /* Font Sizes - Clear hierarchy */
        --font-size-xs: 0.6875rem;            /* 11px - Micro labels */
        --font-size-sm: 0.75rem;              /* 12px - Captions, metadata */
        --font-size-base: 0.875rem;           /* 14px - Body text */
        --font-size-md: 1rem;                 /* 16px - Emphasized body */
        --font-size-lg: 1.125rem;             /* 18px - Card titles */
        --font-size-xl: 1.25rem;              /* 20px - Section headers */
        --font-size-2xl: 1.5rem;              /* 24px - Page titles */
        --font-size-3xl: 2rem;                /* 32px - Large numbers */
        --font-size-4xl: 2.5rem;              /* 40px - Hero numbers */

        /* Font Weights */
        --font-weight-normal: 400;
        --font-weight-medium: 500;
        --font-weight-semibold: 600;
        --font-weight-bold: 700;

        /* Line Heights */
        --line-height-tight: 1.1;             /* Numbers, headings */
        --line-height-snug: 1.25;             /* Compact text */
        --line-height-normal: 1.5;            /* Body text */
        --line-height-relaxed: 1.625;         /* Readable paragraphs */

        /* Letter Spacing */
        --letter-spacing-tight: -0.025em;     /* Large headings */
        --letter-spacing-normal: 0;
        --letter-spacing-wide: 0.025em;       /* All caps labels */
        --letter-spacing-wider: 0.05em;       /* Section headers */

        /* ------------------------------------------------------------------
           3. SPACING (8px Grid System)
           ------------------------------------------------------------------ */

        --space-0: 0;
        --space-1: 0.25rem;                   /* 4px */
        --space-2: 0.5rem;                    /* 8px - Base unit */
        --space-3: 0.75rem;                   /* 12px */
        --space-4: 1rem;                      /* 16px */
        --space-5: 1.25rem;                   /* 20px */
        --space-6: 1.5rem;                    /* 24px */
        --space-8: 2rem;                      /* 32px */
        --space-10: 2.5rem;                   /* 40px */
        --space-12: 3rem;                     /* 48px */
        --space-16: 4rem;                     /* 64px */

        /* Component-specific spacing */
        --card-padding: var(--space-5);       /* 20px */
        --card-padding-sm: var(--space-4);    /* 16px */
        --section-gap: var(--space-6);        /* 24px between sections */
        --element-gap: var(--space-3);        /* 12px between elements */

        /* ------------------------------------------------------------------
           4. BORDERS & RADIUS
           ------------------------------------------------------------------ */

        --radius-sm: 4px;
        --radius-md: 6px;
        --radius-lg: 8px;
        --radius-xl: 12px;
        --radius-2xl: 16px;
        --radius-full: 9999px;

        --border-width: 1px;
        --border-width-thick: 2px;
        --border-accent-width: 4px;           /* Left accent borders */

        /* ------------------------------------------------------------------
           5. SHADOWS (Elevation)
           ------------------------------------------------------------------ */

        --shadow-xs: 0 1px 2px var(--shadow-color);
        --shadow-sm: 0 1px 3px var(--shadow-color), 0 1px 2px var(--shadow-color);
        --shadow-md: 0 4px 6px -1px var(--shadow-color), 0 2px 4px -1px var(--shadow-color);
        --shadow-lg: 0 10px 15px -3px var(--shadow-color), 0 4px 6px -2px var(--shadow-color);
        --shadow-xl: 0 20px 25px -5px var(--shadow-color-heavy), 0 10px 10px -5px var(--shadow-color);

        /* Hover elevation */
        --shadow-hover: 0 8px 20px var(--shadow-color-heavy);

        /* ------------------------------------------------------------------
           6. MOTION / TRANSITIONS
           ------------------------------------------------------------------ */

        /* Duration */
        --duration-instant: 0ms;
        --duration-fast: 100ms;
        --duration-normal: 200ms;
        --duration-slow: 300ms;

        /* Easing */
        --ease-default: cubic-bezier(0.4, 0, 0.2, 1);    /* Smooth deceleration */
        --ease-in: cubic-bezier(0.4, 0, 1, 1);
        --ease-out: cubic-bezier(0, 0, 0.2, 1);
        --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1); /* Only for special emphasis */

        /* Standard transitions */
        --transition-fast: var(--duration-fast) var(--ease-default);
        --transition-normal: var(--duration-normal) var(--ease-default);
        --transition-slow: var(--duration-slow) var(--ease-default);

        /* Hover transforms */
        --hover-lift: translateY(-2px);
        --hover-lift-subtle: translateY(-1px);
        --active-press: translateY(1px);
    }

    /* ==========================================================================
       BASE STYLES - Applied globally
       ========================================================================== */

    /* Typography Defaults */
    .main .block-container {
        font-family: var(--font-family) !important;
        color: var(--color-text-secondary);
        line-height: var(--line-height-normal);
    }

    /* Page Title */
    .page-header-title {
        font-size: var(--font-size-2xl) !important;
        font-weight: var(--font-weight-bold) !important;
        color: var(--color-text-primary) !important;
        line-height: var(--line-height-tight) !important;
        letter-spacing: var(--letter-spacing-tight) !important;
        margin: 0 !important;
    }

    /* Section Title */
    .section-title {
        font-size: var(--font-size-xs) !important;
        font-weight: var(--font-weight-semibold) !important;
        color: var(--color-text-tertiary) !important;
        text-transform: uppercase !important;
        letter-spacing: var(--letter-spacing-wider) !important;
        display: flex !important;
        align-items: center !important;
        gap: var(--space-2) !important;
        margin-bottom: var(--space-4) !important;
        padding: 0 !important;
    }

    .section-title-icon {
        width: 6px;
        height: 6px;
        background: var(--color-brand-primary);
        border-radius: var(--radius-full);
    }

    /* Card Title */
    .card-title {
        font-size: var(--font-size-base) !important;
        font-weight: var(--font-weight-semibold) !important;
        color: var(--color-text-primary) !important;
        margin-bottom: var(--space-1) !important;
    }

    /* Card Subtitle / Meta */
    .card-subtitle, .card-meta {
        font-size: var(--font-size-sm) !important;
        color: var(--color-text-muted) !important;
        font-weight: var(--font-weight-normal) !important;
    }

    /* Numeric Values - More prominent than labels */
    .value-primary {
        font-size: var(--font-size-4xl) !important;
        font-weight: var(--font-weight-bold) !important;
        line-height: var(--line-height-tight) !important;
        color: var(--color-text-primary) !important;
    }

    .value-secondary {
        font-size: var(--font-size-3xl) !important;
        font-weight: var(--font-weight-bold) !important;
        line-height: var(--line-height-tight) !important;
    }

    .value-label {
        font-size: var(--font-size-sm) !important;
        font-weight: var(--font-weight-medium) !important;
        color: var(--color-text-secondary) !important;
    }

    /* Standard Card */
    .ds-card {
        background: var(--color-bg-primary);
        border: var(--border-width) solid var(--color-border-light);
        border-radius: var(--radius-xl);
        padding: var(--card-padding);
        transition: all var(--transition-normal);
    }

    .ds-card:hover {
        border-color: var(--color-border-default);
        box-shadow: var(--shadow-hover);
        transform: var(--hover-lift-subtle);
    }

    /* Semantic Status Indicators */
    .status-success { color: var(--color-success); }
    .status-warning { color: var(--color-warning); }
    .status-critical { color: var(--color-critical); }
    .status-info { color: var(--color-info); }
    .status-neutral { color: var(--color-neutral); }

    .bg-success { background: var(--color-success-bg); }
    .bg-warning { background: var(--color-warning-bg); }
    .bg-critical { background: var(--color-critical-bg); }
    .bg-info { background: var(--color-info-bg); }
    .bg-neutral { background: var(--color-neutral-bg); }

    /* Accent Borders */
    .border-success { border-left: var(--border-accent-width) solid var(--color-success) !important; }
    .border-warning { border-left: var(--border-accent-width) solid var(--color-warning) !important; }
    .border-critical { border-left: var(--border-accent-width) solid var(--color-critical) !important; }
    .border-info { border-left: var(--border-accent-width) solid var(--color-info) !important; }
    .border-neutral { border-left: var(--border-accent-width) solid var(--color-neutral) !important; }

    /* Badge / Pill */
    .ds-badge {
        display: inline-flex;
        align-items: center;
        padding: var(--space-1) var(--space-2);
        font-size: var(--font-size-xs);
        font-weight: var(--font-weight-medium);
        border-radius: var(--radius-full);
        line-height: 1;
    }

    .ds-badge-success {
        background: var(--color-success-light);
        color: var(--color-success-dark);
    }

    .ds-badge-warning {
        background: var(--color-warning-light);
        color: var(--color-warning-dark);
    }

    .ds-badge-critical {
        background: var(--color-critical-light);
        color: var(--color-critical-dark);
    }

    .ds-badge-info {
        background: var(--color-info-light);
        color: var(--color-info-dark);
    }

    /* ===== SIDEBAR - Dark Theme ===== */
    [data-testid="stSidebar"] {
        background-color: var(--color-sidebar-bg) !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        background-color: var(--color-sidebar-bg) !important;
    }

    /* Sidebar Section Headers */
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--color-text-tertiary) !important;
        font-size: var(--font-size-xs) !important;
        font-weight: var(--font-weight-semibold) !important;
        letter-spacing: var(--letter-spacing-wide) !important;
        text-transform: uppercase !important;
        margin-top: var(--space-6) !important;
        margin-bottom: var(--space-2) !important;
        padding-left: var(--space-3) !important;
    }

    [data-testid="stSidebar"] .stMarkdown p {
        color: var(--color-text-muted) !important;
    }

    /* ===== SIDEBAR NAVIGATION BUTTONS ===== */
    /* Base container styles - remove all focus indicators */
    [data-testid="stSidebar"] .stButton,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Default button style (non-selected) */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 8px 8px 0 !important;
        padding: var(--space-3) var(--space-4) !important;
        font-weight: var(--font-weight-normal) !important;
        font-size: var(--font-size-base) !important;
        text-align: left !important;
        justify-content: flex-start !important;
        cursor: pointer !important;
        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Hover state - only shows while mouse is actually hovering */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: rgba(249, 115, 22, 0.08) !important;
        color: #f97316 !important;
        border-left: 3px solid transparent !important;
    }

    /* Secondary button (non-active pages) - ALWAYS transparent unless hovering */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"],
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:link,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:visited {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Secondary button focus/active/focus-within - FORCE transparent */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus-visible,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus-within,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:active,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:target,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"][data-focus],
    [data-testid="stSidebar"] .stButton > button[kind="secondary"][aria-selected="true"] {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Secondary button - not hover state specifically */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:not(:hover) {
        background: transparent !important;
        color: var(--color-text-muted) !important;
    }

    /* Primary button (ACTIVE/SELECTED page) - this is the only one with highlight */
    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:focus,
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:focus-visible,
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:active {
        background: rgba(249, 115, 22, 0.15) !important;
        color: #f97316 !important;
        font-weight: 500 !important;
        border: none !important;
        border-left: 3px solid #f97316 !important;
        border-radius: 0 8px 8px 0 !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Primary button hover - slightly darker */
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: rgba(249, 115, 22, 0.2) !important;
    }

    /* Remove ALL focus rings globally in sidebar */
    [data-testid="stSidebar"] button:focus,
    [data-testid="stSidebar"] button:focus-visible,
    [data-testid="stSidebar"] button:focus-within,
    [data-testid="stSidebar"] *:focus,
    [data-testid="stSidebar"] *:focus-visible {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Override any Streamlit default active/focus backgrounds for secondary buttons */
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:focus,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:active,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button:focus,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button:active {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* ===== SIDEBAR BRAND ===== */
    .sidebar-brand {
        padding: 20px 16px 16px 16px;
        margin-bottom: 0;
        text-align: center;
    }

    .sidebar-brand img {
        height: 28px !important;
        margin-bottom: 2px;
    }

    .sidebar-brand p {
        color: #64748b !important;
        font-size: 11px !important;
        margin: 0 !important;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* ===== USER INFO CARD ===== */
    .user-info-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 8px;
        padding: 12px 14px;
        margin: 8px 12px 12px 12px;
        border: 1px solid #334155;
    }

    .user-info-card .user-name {
        color: #f8fafc;
        font-weight: 600;
        font-size: 13px;
        margin-bottom: 2px;
    }

    .user-info-card .user-role {
        color: #94a3b8;
        font-size: 11px;
    }

    /* ===== CONNECTION STATUS ===== */
    .connection-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 500;
        margin: 8px 12px;
    }

    .status-connected {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
    }

    .status-disconnected {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
    }

    /* ===== NAV SECTION HEADERS ===== */
    .nav-section-header {
        color: #64748b;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 16px 16px 6px 16px;
        margin: 0;
    }

    /* ===== ROLE BADGE ENHANCED ===== */
    .role-badge-compact {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .role-badge-compact.admin {
        background: rgba(249, 115, 22, 0.15);
        color: #f97316;
    }

    .role-badge-compact.operations {
        background: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
    }

    .role-badge-compact.finance {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
    }

    /* ===== SIDEBAR FOOTER ===== */
    .sidebar-footer {
        text-align: center;
        padding: 12px;
        border-top: 1px solid #334155;
        margin-top: 8px;
    }

    .sidebar-footer .version {
        color: #475569;
        font-size: 10px;
    }

    .sidebar-footer .tech {
        color: #f97316;
        font-size: 10px;
        font-weight: 500;
    }

    /* ===== MAIN CONTENT AREA ===== */
    .main .block-container {
        background-color: #f8fafc;
        padding: 1.5rem 2rem;
        max-width: 100%;
    }

    /* ===== PAGE HEADER ===== */
    .main-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1.5rem;
    }

    .sub-header {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        margin: 1.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* ===== METRIC CARDS ===== */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        cursor: pointer;
        transition: all 0.2s ease;
    }

    [data-testid="stMetric"]:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        transform: translateY(-2px);
    }

    [data-testid="stMetric"]::after {
        content: "Click to view details";
        position: absolute;
        bottom: -24px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 11px;
        color: #64748b;
        opacity: 0;
        transition: opacity 0.2s ease;
        white-space: nowrap;
    }

    [data-testid="stMetric"]:hover::after {
        opacity: 1;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
    }

    [data-testid="stMetricValue"] {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 1.75rem !important;
    }

    /* ===== LOADING SKELETONS ===== */
    @keyframes skeleton-pulse {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 0.8; }
    }

    .skeleton {
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 4px;
    }

    .skeleton-row {
        height: 40px;
        margin-bottom: 8px;
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 4px;
    }

    .skeleton-chart {
        height: 200px;
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 8px;
    }

    /* ===== EMPTY STATE ===== */
    .empty-state {
        text-align: center;
        padding: 48px 24px;
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
    }

    .empty-state-title {
        font-size: 16px;
        font-weight: 600;
        color: #475569;
        margin-bottom: 8px;
    }

    .empty-state-message {
        font-size: 14px;
        color: #64748b;
        margin: 0;
    }

    /* ===== CLICKABLE CARDS ===== */
    .clickable-card {
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }

    .clickable-card:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.12);
        transform: translateY(-1px);
    }

    /* ===== TABLE HOVER ===== */
    [data-testid="stDataFrame"] tbody tr {
        transition: background-color 0.15s ease;
    }

    [data-testid="stDataFrame"] tbody tr:hover {
        background-color: #f1f5f9 !important;
    }

    /* ===== BUTTONS ===== */
    .main .stButton > button {
        background: #22c55e;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 0.875rem;
        transition: all 0.15s ease;
    }

    .main .stButton > button:hover {
        background: #16a34a;
    }

    /* ===== TAB STYLING ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: transparent;
        border-bottom: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 12px 20px;
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: #64748b !important;
        font-weight: 500;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #1e293b !important;
    }

    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #f97316 !important;
        border-bottom: 2px solid #f97316 !important;
    }

    /* ===== ALERTS ===== */
    .stAlert {
        border-radius: 8px;
        border: none;
    }

    /* ===== DATA TABLE ===== */
    .stDataFrame {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
    }

    /* ===== FORM ===== */
    .stForm {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }

    /* ===== EXPANDER ===== */
    .streamlit-expanderHeader {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-weight: 500;
        color: #1e293b;
    }

    /* ===== INPUT FIELDS ===== */
    .stSelectbox > div > div,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stTextArea textarea,
    .stDateInput > div > div > input {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        color: #1e293b !important;
    }

    /* Text area specific - ensure visible border */
    .stTextArea textarea,
    [data-testid="stTextArea"] textarea {
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        background: #ffffff !important;
    }

    .stSelectbox > div > div:focus-within,
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #f97316 !important;
        box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1) !important;
    }

    /* ===== MULTISELECT DROPDOWN ===== */
    .stMultiSelect > div > div {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        color: #1e293b !important;
        min-height: 42px !important;
    }

    .stMultiSelect > div > div:hover {
        border-color: #cbd5e1 !important;
    }

    .stMultiSelect > div > div:focus-within {
        border-color: #f97316 !important;
        box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1) !important;
    }

    /* Multiselect placeholder text */
    .stMultiSelect [data-baseweb="select"] > div:first-child {
        color: #64748b !important;
    }

    /* ===== PLOTLY CHARTS ===== */
    .stPlotlyChart {
        background-color: transparent;
        border-radius: 0;
        padding: 0;
        border: none;
    }

    /* Hide Plotly modebar (toolbar) for cleaner look */
    .js-plotly-plot .plotly .modebar,
    .modebar-container,
    .modebar,
    .modebar-group,
    [data-title="Zoom"],
    [data-title="Pan"],
    [data-title="Box Select"],
    [data-title="Lasso Select"],
    .plotly .modebar {
        display: none !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Also hide for iframe-based plotly charts */
    iframe[title*="plotly"] .modebar {
        display: none !important;
    }

    /* ===== DIVIDER ===== */
    hr {
        border: none !important;
        border-top: 1px solid #e2e8f0 !important;
        margin: 1.5rem 0 !important;
    }

    /* ===== STREAMLIT SPINNER ===== */
    .stSpinner > div {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    }

    .stSpinner > div > div {
        border-color: #f97316 !important;
        border-right-color: transparent !important;
    }

    /* Page transition effect */
    .main .block-container {
        animation: fadeIn 0.3s ease-in-out;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
    }

    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* ===== CHECKBOX ===== */
    .stCheckbox label {
        color: #1e293b !important;
        font-weight: 400;
    }

    /* ===== DOWNLOAD BUTTON ===== */
    .stDownloadButton > button {
        background: transparent !important;
        color: #f97316 !important;
        border: 1px solid #f97316 !important;
    }

    .stDownloadButton > button:hover {
        background: rgba(249, 115, 22, 0.1) !important;
    }

    /* ===== DASHBOARD SECTIONS ===== */
    .dashboard-section {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }

    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-title:first-of-type {
        margin-top: 0;
    }

    .section-title-icon {
        width: 8px;
        height: 8px;
        background: #f97316;
        border-radius: 2px;
    }

    /* ===== ADMIN DASHBOARD HIERARCHY ===== */
    .admin-section {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }

    .admin-section.critical {
        border-left: 4px solid #dc2626;
        background: linear-gradient(to right, #fef2f2 0%, #ffffff 100%);
    }

    .admin-section.operational {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(to right, #eff6ff 0%, #ffffff 100%);
    }

    .admin-section.revenue {
        border-left: 4px solid #10b981;
        background: linear-gradient(to right, #ecfdf5 0%, #ffffff 100%);
    }

    .admin-section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .admin-section-icon {
        font-size: 1.25rem;
    }

    .admin-section-title {
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    .admin-section.critical .admin-section-title {
        color: #dc2626;
    }

    .admin-section.operational .admin-section-title {
        color: #3b82f6;
    }

    .admin-section.revenue .admin-section-title {
        color: #10b981;
    }

    .admin-section-subtitle {
        font-size: 0.75rem;
        color: #6b7280;
        margin-left: auto;
    }

    .priority-badge {
        font-size: 0.65rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .priority-badge.high {
        background: #fef2f2;
        color: #dc2626;
    }

    .priority-badge.medium {
        background: #eff6ff;
        color: #3b82f6;
    }

    .priority-badge.low {
        background: #ecfdf5;
        color: #10b981;
    }

    /* ===== KPI CARD BUTTONS ===== */
    .kpi-button-container .stButton > button {
        background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 1.25rem 1rem !important;
        min-height: 120px !important;
        color: #1e293b !important;
        font-size: 0.85rem !important;
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.6 !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        position: relative !important;
        overflow: hidden !important;
    }

    .kpi-button-container .stButton > button::before {
        content: '' !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        height: 3px !important;
        background: linear-gradient(90deg, #f97316, #fb923c) !important;
        opacity: 0 !important;
        transition: opacity 0.25s ease !important;
    }

    .kpi-button-container .stButton > button:hover {
        border-color: #f97316 !important;
        box-shadow: 0 8px 24px rgba(249, 115, 22, 0.15) !important;
        transform: translateY(-4px) !important;
        background: linear-gradient(135deg, #fffbf7 0%, #fff7f0 100%) !important;
    }

    .kpi-button-container .stButton > button:hover::before {
        opacity: 1 !important;
    }

    .kpi-button-container .stButton > button:active {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.12) !important;
    }

    .kpi-button-container .stButton > button:focus {
        outline: 2px solid #f97316 !important;
        outline-offset: 2px !important;
    }

    /* ===== ALERT CARDS ===== */
    .alert-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        border-left: 4px solid;
        margin-bottom: 0.5rem;
    }

    .alert-card.warning {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }

    .alert-card.success {
        border-left-color: #22c55e;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }

    .alert-card.info {
        border-left-color: #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }

    /* ===== CLICKABLE ALERT BUTTONS ===== */
    .alert-button-container .stButton > button {
        background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%) !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 4px solid #22c55e !important;
        border-radius: 10px !important;
        padding: 1rem 1.25rem !important;
        min-height: 80px !important;
        color: #1e293b !important;
        font-size: 0.85rem !important;
        white-space: pre-line !important;
        text-align: left !important;
        line-height: 1.5 !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03) !important;
        cursor: pointer !important;
    }

    .alert-button-container .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(0,0,0,0.08) !important;
    }

    .alert-button-container .stButton > button:focus {
        outline: 2px solid #f97316 !important;
        outline-offset: 2px !important;
    }

    .alert-button-container .stButton > button:active {
        transform: translateY(-1px) !important;
    }

    /* Alert button variants */
    .alert-warning .stButton > button {
        border-left-color: #f59e0b !important;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%) !important;
    }

    .alert-warning .stButton > button:hover {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
        box-shadow: 0 6px 16px rgba(245, 158, 11, 0.15) !important;
    }

    .alert-success .stButton > button {
        border-left-color: #22c55e !important;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%) !important;
    }

    .alert-success .stButton > button:hover {
        background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%) !important;
        box-shadow: 0 6px 16px rgba(34, 197, 94, 0.15) !important;
    }

    .alert-info .stButton > button {
        border-left-color: #3b82f6 !important;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%) !important;
    }

    .alert-info .stButton > button:hover {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.15) !important;
    }

    /* ===== QUICK ACTION SECTION ===== */
    .quick-action-wrapper {
        background: linear-gradient(135deg, var(--color-sidebar-bg) 0%, #334155 100%);
        border-radius: var(--radius-xl) var(--radius-xl) 0 0;
        padding: var(--space-3) var(--space-5);
        margin-top: var(--space-2);
        margin-bottom: -1px;
    }

    .quick-action-title {
        color: var(--color-text-muted);
        font-size: var(--font-size-xs);
        font-weight: var(--font-weight-semibold);
        letter-spacing: var(--letter-spacing-wide);
        text-transform: uppercase;
        margin: 0;
    }

    .qa-buttons-row {
        background: linear-gradient(135deg, var(--color-sidebar-bg) 0%, #334155 100%);
        border-radius: 0 0 var(--radius-xl) var(--radius-xl);
        padding: 0 var(--space-4) var(--space-4) var(--space-4);
        margin-top: calc(-1 * var(--space-4));
    }

    .qa-buttons-row .stButton > button {
        background: rgba(255, 255, 255, 0.1) !important;
        color: var(--color-text-inverse) !important;
        border: var(--border-width) solid rgba(255, 255, 255, 0.2) !important;
        border-radius: var(--radius-lg) !important;
        padding: var(--space-3) var(--space-3) !important;
        font-size: var(--font-size-base) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        min-height: 50px !important;
    }

    .qa-buttons-row .stButton > button:hover {
        background: #f97316 !important;
        border-color: #f97316 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4) !important;
    }

    .qa-buttons-row .stButton > button:focus {
        outline: 2px solid #fb923c !important;
        outline-offset: 2px !important;
    }

    .qa-buttons-row .stButton > button:disabled {
        background: rgba(100, 116, 139, 0.2) !important;
        color: rgba(255, 255, 255, 0.4) !important;
        border-color: rgba(255, 255, 255, 0.1) !important;
        cursor: not-allowed !important;
        transform: none !important;
    }

    .qa-buttons-row .stButton > button:disabled:hover {
        background: rgba(100, 116, 139, 0.2) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    .qa-buttons-row p, .qa-buttons-row .stCaption p {
        color: rgba(255, 255, 255, 0.5) !important;
        font-size: 0.7rem !important;
        margin-top: 0.25rem !important;
    }

    /* ===== BILLING INSIGHTS SECTION ===== */
    .billing-container {
        background: linear-gradient(135deg, #fefefe 0%, #f8fafc 100%);
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        display: flex;
        gap: 1.5rem;
        align-items: stretch;
    }

    .billing-card {
        flex: 1;
        background: #ffffff;
        border-radius: 10px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        position: relative;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }

    .billing-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }

    .billing-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, #22c55e, #16a34a);
        border-radius: 4px 0 0 4px;
    }

    .billing-card.revenue::before {
        background: linear-gradient(180deg, #f97316, #ea580c);
    }

    .billing-card-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        margin-bottom: 0.75rem;
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    }

    .billing-card.revenue .billing-card-icon {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    }

    .billing-card-label {
        color: #64748b;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    .billing-card-value {
        color: #1e293b;
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        line-height: 1.2;
    }

    .billing-card-subtitle {
        color: #94a3b8;
        font-size: 0.75rem;
        margin-bottom: 0.75rem;
    }

    .billing-card-footer {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-top: 0.75rem;
        border-top: 1px solid #f1f5f9;
        color: #64748b;
        font-size: 0.7rem;
    }

    .billing-card-footer .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #22c55e;
    }

    .billing-card.revenue .billing-card-footer .dot {
        background: #f97316;
    }

    .billing-info-card {
        flex: 1.2;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 10px;
        padding: 1.25rem;
        color: #ffffff;
    }

    .billing-info-title {
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }

    .billing-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .billing-info-row:last-child {
        border-bottom: none;
        padding-top: 0.75rem;
        margin-top: 0.25rem;
    }

    .billing-info-label {
        color: #94a3b8;
        font-size: 0.8rem;
    }

    .billing-info-value {
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .billing-info-row.total .billing-info-label {
        color: #f97316;
        font-weight: 600;
    }

    .billing-info-row.total .billing-info-value {
        color: #f97316;
        font-size: 1.1rem;
    }

    /* ===== ATTENTION TABLE STYLES ===== */
    .priority-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
    }

    .priority-high {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
    }

    .priority-medium {
        background: #fffbeb;
        color: #d97706;
        border: 1px solid #fde68a;
    }

    .priority-low {
        background: #f0fdf4;
        color: #16a34a;
        border: 1px solid #bbf7d0;
    }

    .attention-row {
        background: #ffffff;
        border-radius: 8px;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        border: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease;
    }

    .attention-row:hover {
        border-color: #cbd5e1;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .attention-row.urgent {
        border-left: 4px solid #dc2626;
    }

    .attention-row.warning {
        border-left: 4px solid #f59e0b;
    }

    .attention-row.normal {
        border-left: 4px solid #22c55e;
    }

    .attention-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .attention-title {
        font-weight: 600;
        color: #1e293b;
        font-size: 0.9rem;
    }

    .attention-subtitle {
        color: #64748b;
        font-size: 0.8rem;
    }

    .attention-meta {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .attention-days {
        font-size: 0.8rem;
        color: #64748b;
    }

    .attention-days.urgent {
        color: #dc2626;
        font-weight: 600;
    }

    .attention-actions {
        display: flex;
        gap: 0.5rem;
    }

    /* Attention row action buttons */
    div[data-testid="column"]:has(button[key^="fix_"]) .stButton > button,
    div[data-testid="column"]:has(button[key^="vendor_"]) .stButton > button {
        font-size: 0.75rem !important;
        padding: 0.4rem 0.5rem !important;
        min-height: auto !important;
    }

    /* ===== CONFIRMATION MODAL STYLES ===== */
    .confirm-modal {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        margin: 1rem 0;
    }

    .confirm-modal-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .confirm-modal-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    }

    .confirm-modal-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1e293b;
    }

    .confirm-modal-subtitle {
        font-size: 0.85rem;
        color: #64748b;
    }

    .confirm-state-change {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
    }

    .confirm-state {
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .confirm-state.current {
        background: #fee2e2;
        color: #dc2626;
    }

    .confirm-state.next {
        background: #dcfce7;
        color: #16a34a;
    }

    .confirm-arrow {
        color: #94a3b8;
        font-size: 1.25rem;
    }

    .confirm-details {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }

    .confirm-detail-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #e2e8f0;
    }

    .confirm-detail-row:last-child {
        border-bottom: none;
    }

    .confirm-detail-label {
        color: #64748b;
        font-size: 0.85rem;
    }

    .confirm-detail-value {
        color: #1e293b;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .confirm-timestamp {
        text-align: center;
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #f1f5f9;
    }

    /* ===== CHART FILTER BUTTONS ===== */
    div[data-testid="column"]:has(button[key^="status_btn_"]) .stButton > button,
    div[data-testid="column"]:has(button[key^="brand_btn_"]) .stButton > button {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        color: #374151 !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 0.5rem 0.75rem !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        min-height: 40px !important;
        transition: all 0.2s ease !important;
    }

    div[data-testid="column"]:has(button[key^="status_btn_"]) .stButton > button:hover,
    div[data-testid="column"]:has(button[key^="brand_btn_"]) .stButton > button:hover {
        background: linear-gradient(135deg, #f97316 0%, #fb923c 100%) !important;
        color: #ffffff !important;
        border-color: #f97316 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.25) !important;
    }

    /* ===== ROLE BADGE ===== */
    .role-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.4rem 0.85rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    .role-operations {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        color: #1e40af;
        border: 1px solid #93c5fd;
    }

    .role-finance {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        color: #065f46;
        border: 1px solid #6ee7b7;
    }

    .role-admin {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        color: #92400e;
        border: 1px solid #fcd34d;
    }

    /* ===== SLA INDICATORS ===== */
    .sla-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }

    .sla-ok {
        background: #dcfce7;
        color: #166534;
    }

    .sla-warning {
        background: #fef3c7;
        color: #92400e;
    }

    .sla-critical {
        background: #fee2e2;
        color: #dc2626;
        animation: pulse-critical 2s infinite;
    }

    @keyframes pulse-critical {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* ===== ANALYTICS INSIGHT CARDS ===== */
    .insight-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
        position: relative;
    }

    .insight-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }

    .insight-card.warning {
        border-left: 4px solid #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }

    .insight-card.critical {
        border-left: 4px solid #dc2626;
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    }

    .insight-card.success {
        border-left: 4px solid #22c55e;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }

    .insight-card.info {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }

    .insight-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
        display: block;
    }

    .insight-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.5rem;
    }

    .insight-title {
        font-size: 0.7rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }

    .insight-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.2;
    }

    .insight-subtitle {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 0.35rem;
    }

    /* Loading Spinner */
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem;
        min-height: 200px;
    }

    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid #e2e8f0;
        border-top-color: #f97316;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    .loading-text {
        margin-top: 1rem;
        color: #64748b;
        font-size: 0.9rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Skeleton Loading */
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
    }

    .skeleton-card {
        height: 120px;
        margin-bottom: 1rem;
    }

    .skeleton-chart {
        height: 300px;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* Last Updated Badge */
    .last-updated {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.75rem;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        font-size: 0.75rem;
        color: #64748b;
    }

    .last-updated .dot {
        width: 6px;
        height: 6px;
        background: #22c55e;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* Empty State */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: #f8fafc;
        border-radius: 12px;
        border: 2px dashed #e2e8f0;
    }

    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }

    .empty-state-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #374151;
        margin-bottom: 0.5rem;
    }

    .empty-state-text {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1rem;
    }

    /* ===== ANALYTICS SECTION ===== */
    .analytics-section {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        border: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.03);
        margin-bottom: 1.5rem;
    }

    .analytics-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.25rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .analytics-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .analytics-subtitle {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.25rem;
    }

    /* ===== CHART CONTAINER ===== */
    .chart-container {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .chart-title {
        font-size: 0.75rem;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 0.5rem;
        padding: 0.5rem 0;
        border-bottom: none;
    }

    /* ===== CHARTS WRAPPER ===== */
    .charts-row {
        display: flex;
        gap: 1.5rem;
        margin-top: 1rem;
    }

    .chart-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #f1f5f9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ===== ANALYTICS BAR CHART STYLES ===== */
    /* Smooth transitions for bar hover effects */
    .js-plotly-plot .plotly .bars .point path {
        transition: opacity 200ms ease-in-out, fill 200ms ease-in-out;
    }

    /* Muted non-hovered bars when any bar is hovered */
    .js-plotly-plot .plotly:hover .bars .point path {
        opacity: 0.5;
    }

    /* Highlight hovered bar */
    .js-plotly-plot .plotly .bars .point:hover path {
        opacity: 1 !important;
        filter: brightness(0.85);
    }

    /* Cursor pointer on bars */
    .js-plotly-plot .plotly .bars .point {
        cursor: pointer;
    }

    /* Tooltip styling enhancement */
    .js-plotly-plot .hoverlayer .hovertext {
        transition: opacity 150ms ease-in-out;
    }

    /* ===== INVENTORY OVERVIEW KPI CARDS (Reference Style) ===== */
    .kpi-row {
        display: flex;
        gap: 16px;
        margin-bottom: 0;
    }

    .kpi-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 24px 20px;
        border: none;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
        transition: transform 180ms ease-out, box-shadow 180ms ease-out;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        cursor: pointer;
        outline: none;
        -webkit-tap-highlight-color: transparent;
        user-select: none;
        min-height: 130px;
    }

    /* Title - Uppercase, muted, at top */
    .kpi-card-title {
        font-size: 11px;
        font-weight: 600;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 12px;
    }

    /* Value - Large, bold, colored, center focus */
    .kpi-card-value {
        font-size: 42px;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 8px;
        letter-spacing: -1.5px;
    }

    /* Color variants - only applied to value */
    .kpi-card.neutral .kpi-card-value { color: #374151; }
    .kpi-card.blue .kpi-card-value { color: #2563eb; }
    .kpi-card.green .kpi-card-value { color: #16a34a; }
    .kpi-card.amber .kpi-card-value { color: #d97706; }
    .kpi-card.red .kpi-card-value { color: #dc2626; }
    .kpi-card.purple .kpi-card-value { color: #8b5cf6; }
    .kpi-card.gray .kpi-card-value { color: #6b7280; }

    /* Label - Small, muted, below value */
    .kpi-card-label {
        font-size: 13px;
        font-weight: 500;
        color: #6b7280;
        margin: 0;
    }

    /* ===== HOVER STATE (Subtle elevation) ===== */
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04);
    }

    /* ===== ACTIVE STATE (Pressed) ===== */
    .kpi-card:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
        transition-duration: 80ms;
    }

    /* ===== KEYBOARD FOCUS (Minimal) ===== */
    .kpi-card:focus-visible,
    .kpi-card.kpi-focused {
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
    }

    /* ===== TOUCH DEVICES ===== */
    @media (hover: none) {
        .kpi-card {
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        .kpi-card:active {
            background: #fafafa;
        }
    }

    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {
        .kpi-card {
            padding: 20px 16px;
            min-height: 110px;
        }
        .kpi-card-value {
            font-size: 32px;
        }
    }

    /* KPI Cards Row Layout - Flexbox for clean single row */
    .kpi-cards-row {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
    }
    .kpi-cards-row .kpi-card {
        flex: 1;
        min-width: 0;
    }

    /* ===== KPI CARD ANCHOR LINKS (No underlines) ===== */
    .kpi-cards-row a,
    .kpi-cards-row a:hover,
    .kpi-cards-row a:focus,
    .kpi-cards-row a:active,
    .kpi-cards-row a:visited {
        text-decoration: none !important;
        color: inherit !important;
    }
    .kpi-cards-row a * {
        text-decoration: none !important;
    }

    /* ===== CLICKABLE METRIC CARDS ===== */
    .clickable-card {
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .clickable-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    .clickable-card:active {
        transform: translateY(0);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    }

    /* Hide Plotly modebar using CSS */
    .modebar-container, .modebar, .modebar-group, [class*="modebar"] {
        display: none !important;
    }

    /* Hide any stray iframes with zero height */
    iframe[height="0"] {
        display: none !important;
        visibility: hidden !important;
        position: absolute !important;
        left: -9999px !important;
    }

    /* ===== MERGED CARD + BUTTON STYLING ===== */
    /* Card and button appear as one seamless clickable element */

    /* KPI Cards - remove bottom radius to connect with button */
    .kpi-card {
        border-radius: 10px 10px 0 0 !important;
        margin-bottom: 0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
    }

    /* Metric Cards - remove bottom radius to connect with button */
    .metric-card {
        border-radius: 12px 12px 0 0 !important;
        margin-bottom: 0 !important;
    }

    /* Style buttons in columns to look like card footer */
    [data-testid="column"] [data-testid="stButton"] {
        margin-top: -1px !important;
    }

    [data-testid="column"] [data-testid="stButton"] button {
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-top: 1px solid #e5e7eb !important;
        border-radius: 0 0 10px 10px !important;
        color: #64748b !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 10px 16px !important;
        transition: all 0.15s ease !important;
    }

    [data-testid="column"] [data-testid="stButton"] button:hover {
        background: #f1f5f9 !important;
        color: #3b82f6 !important;
        border-color: #cbd5e1 !important;
    }

    /* Combined hover effect - card + button lift together */
    [data-testid="column"]:hover .kpi-card,
    [data-testid="column"]:hover .metric-card {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    [data-testid="column"]:hover [data-testid="stButton"] button {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    /* ===== ASSETS SEARCH FORM STYLING ===== */
    /* Primary Search button - Orange */
    [data-testid="stBaseButton-primaryFormSubmit"],
    [data-testid="stForm"] button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #f97316, #ea580c) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 10px 24px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(249, 115, 22, 0.3) !important;
    }
    [data-testid="stBaseButton-primaryFormSubmit"]:hover,
    [data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
        background: linear-gradient(135deg, #ea580c, #dc2626) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* Secondary Clear button - Ghost style */
    [data-testid="stBaseButton-secondaryFormSubmit"],
    [data-testid="stBaseButton-formSubmit"],
    [data-testid="stForm"] button[kind="secondaryFormSubmit"],
    [data-testid="stForm"] button[kind="formSubmit"] {
        background: transparent !important;
        color: #6b7280 !important;
        border: 1px solid #d1d5db !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 10px 24px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stBaseButton-secondaryFormSubmit"]:hover,
    [data-testid="stBaseButton-formSubmit"]:hover,
    [data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover,
    [data-testid="stForm"] button[kind="formSubmit"]:hover {
        background: #f3f4f6 !important;
        color: #374151 !important;
        border-color: #9ca3af !important;
    }

    /* ===== ACTIVE FILTER PILLS ===== */
    .filter-pills-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 8px 0;
        align-items: center;
    }
    .filter-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }
    .filter-pill-label {
        color: #6b7280;
        font-weight: 400;
    }
    .filter-pills-title {
        font-size: 12px;
        color: #9ca3af;
        font-weight: 500;
        margin-right: 4px;
    }

    /* ===== PAGINATION NAVIGATION ===== */
    /* Active page button - Orange */
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #f97316, #ea580c) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        box-shadow: 0 2px 6px rgba(249, 115, 22, 0.35) !important;
    }
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #ea580c, #dc2626) !important;
        box-shadow: 0 3px 10px rgba(249, 115, 22, 0.45) !important;
    }

    /* ===== ASSET QUICK ACTIONS PANEL ===== */
    .asset-detail-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
    }
    .asset-detail-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #f3f4f6;
    }
    .asset-detail-serial {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
    }
    .asset-detail-status {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .asset-detail-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
    }
    .asset-detail-item {
        padding: 8px 0;
    }
    .asset-detail-item-label {
        font-size: 11px;
        font-weight: 600;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .asset-detail-item-value {
        font-size: 14px;
        font-weight: 500;
        color: #374151;
    }

</style>
"""
