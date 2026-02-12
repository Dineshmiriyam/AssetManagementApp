"""
Analytics chart components — extracted from app.py.
Reusable chart builders used across Dashboard, Assignments, Billing pages.
"""

import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events


def create_analytics_bar_chart(
    x_data: list,
    y_data: list,
    x_label: str,
    y_label: str,
    title: str = None,
    height: int = 350,
    hover_context: str = "Count",
    total_for_percent: int = None,
    click_key: str = None
) -> go.Figure:
    """
    Create an analytics-grade bar chart with clarity-focused design.

    Features:
    - Clear axis labels with proper typography
    - Light, non-distracting gridlines
    - Muted base color with hover highlight
    - Rich tooltips with context and percentages
    - Smooth 200ms transitions
    - Click-to-filter support via session state

    Args:
        x_data: List of x-axis values (categories)
        y_data: List of y-axis values (counts)
        x_label: Label for x-axis
        y_label: Label for y-axis
        title: Optional chart title
        height: Chart height in pixels
        hover_context: Context label for hover (e.g., "Assets", "Count")
        total_for_percent: Total value for percentage calculation in tooltip
        click_key: Session state key for click filtering

    Returns:
        Plotly Figure object with analytics-grade styling
    """
    # Calculate percentages if total provided
    if total_for_percent and total_for_percent > 0:
        percentages = [(v / total_for_percent * 100) for v in y_data]
        hover_template = (
            '<b style="font-size:14px">%{x}</b><br>'
            f'<span style="color:#6B7280">{hover_context}:</span> '
            '<b>%{y:,}</b><br>'
            '<span style="color:#6B7280">Share:</span> '
            '<b>%{customdata:.1f}%</b>'
            '<extra></extra>'
        )
        customdata = percentages
    else:
        hover_template = (
            '<b style="font-size:14px">%{x}</b><br>'
            f'<span style="color:#6B7280">{hover_context}:</span> '
            '<b>%{y:,}</b>'
            '<extra></extra>'
        )
        customdata = None

    # Professional color palette - vibrant but clean
    colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899', '#84CC16']
    bar_colors = [colors[i % len(colors)] for i in range(len(x_data))]

    # Create bar trace
    bar_trace = go.Bar(
        x=x_data,
        y=y_data,
        marker=dict(
            color=bar_colors,
            line=dict(width=0)
        ),
        hovertemplate=hover_template,
        customdata=customdata,
        hoverlabel=dict(
            bgcolor='#1F2937',
            bordercolor='#374151',
            font=dict(
                family='Inter, -apple-system, sans-serif',
                size=13,
                color='#FFFFFF'
            ),
            align='left'
        )
    )

    fig = go.Figure(data=[bar_trace])

    # Analytics-grade layout
    fig.update_layout(
        height=height,
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        font=dict(
            family='Inter, -apple-system, sans-serif',
            size=12,
            color='#374151'
        ),
        margin=dict(t=20, b=60, l=50, r=20),
        showlegend=False,

        # X-axis styling
        xaxis=dict(
            title=dict(
                text=x_label,
                font=dict(size=12, color='#4B5563'),
                standoff=12
            ),
            tickfont=dict(size=11, color='#6B7280'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB',
            linewidth=1,
            type='category',
            tickangle=0 if len(x_data) <= 6 else -45
        ),

        # Y-axis styling with light gridlines
        yaxis=dict(
            title=dict(
                text=y_label,
                font=dict(size=12, color='#4B5563'),
                standoff=12
            ),
            tickfont=dict(size=11, color='#9CA3AF'),
            showgrid=True,
            gridcolor='#F3F4F6',
            gridwidth=1,
            griddash='solid',
            showline=True,
            linecolor='#E5E7EB',
            linewidth=1,
            rangemode='tozero',
            zeroline=True,
            zerolinecolor='#E5E7EB',
            zerolinewidth=1
        ),

        # Bar spacing
        bargap=0.3,

        # Smooth transitions
        transition=dict(
            duration=200,
            easing='cubic-in-out'
        ),

        # Hover mode - closest bar, no spike line
        hovermode='closest',
        hoverdistance=30
    )

    # Disable spike lines completely
    fig.update_xaxes(
        showspikes=False,
        spikemode=None
    )
    fig.update_yaxes(
        showspikes=False,
        spikemode=None
    )

    # Update hover behavior
    fig.update_traces(
        hoverlabel=dict(namelength=0),
        selector=dict(type='bar')
    )

    return fig
