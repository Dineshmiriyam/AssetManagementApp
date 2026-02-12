"""
Loading skeleton and state management components — extracted from app.py.
Skeleton loaders for tables, charts, cards, and loading state helpers.
"""

import streamlit as st


def render_loading_skeleton(skeleton_type: str = "table", rows: int = 5) -> None:
    """Render loading skeleton placeholders."""
    if skeleton_type == "table":
        skeleton_html = '<div style="padding: 16px;">'
        # Header row
        skeleton_html += '<div style="height: 32px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 4px; margin-bottom: 12px;"></div>'
        # Data rows
        for _ in range(rows):
            skeleton_html += '<div style="height: 44px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 4px; margin-bottom: 8px;"></div>'
        skeleton_html += '</div>'
        st.markdown(skeleton_html, unsafe_allow_html=True)

    elif skeleton_type == "chart":
        st.markdown("""
        <div style="height: 250px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
            <span style="color: #94a3b8; font-size: 14px;">Loading chart...</span>
        </div>
        """, unsafe_allow_html=True)

    elif skeleton_type == "cards":
        cols = st.columns(4)
        for col in cols:
            with col:
                st.markdown("""
                <div style="height: 100px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 8px;"></div>
                """, unsafe_allow_html=True)


def render_skeleton_card(width: str = "100%", height: str = "120px"):
    """Render a skeleton loader for metric cards."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        width: {width};
        height: {height};
    "></div>
    <style>
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_table(rows: int = 5, cols: int = 4):
    """Render a skeleton loader for data tables."""
    header_html = "".join([f'<div class="skeleton-cell" style="flex: 1;"></div>' for _ in range(cols)])
    rows_html = ""
    for _ in range(rows):
        cells = "".join([f'<div class="skeleton-cell" style="flex: 1; height: 20px;"></div>' for _ in range(cols)])
        rows_html += f'<div class="skeleton-row">{cells}</div>'

    st.markdown(f"""
    <div class="skeleton-table">
        <div class="skeleton-header">{header_html}</div>
        {rows_html}
    </div>
    <style>
        .skeleton-table {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }}
        .skeleton-header {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .skeleton-row {{
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
        }}
        .skeleton-cell {{
            background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
            height: 30px;
        }}
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_chart(height: str = "300px"):
    """Render a skeleton loader for charts."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        height: {height};
        display: flex;
        align-items: center;
        justify-content: center;
    ">
        <div style="color: #94a3b8; font-size: 0.9rem;">Loading chart...</div>
    </div>
    <style>
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_metrics(count: int = 4):
    """Render skeleton loaders for a row of metric cards."""
    cols = st.columns(count)
    for col in cols:
        with col:
            render_skeleton_card(height="100px")


def render_loading_overlay(message: str = "Processing..."):
    """Render a loading overlay for async operations."""
    st.markdown(f"""
    <div style="
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
    ">
        <div style="
            width: 40px;
            height: 40px;
            border: 3px solid #e2e8f0;
            border-top: 3px solid #f97316;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px auto;
        "></div>
        <div style="color: #64748b; font-size: 0.95rem;">{message}</div>
    </div>
    <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
    """, unsafe_allow_html=True)


def init_loading_state(key: str):
    """Initialize a loading state in session state."""
    if f"loading_{key}" not in st.session_state:
        st.session_state[f"loading_{key}"] = False


def set_loading(key: str, is_loading: bool):
    """Set loading state for a specific operation."""
    st.session_state[f"loading_{key}"] = is_loading


def is_loading(key: str) -> bool:
    """Check if an operation is currently loading."""
    return st.session_state.get(f"loading_{key}", False)
