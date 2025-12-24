import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# UMass Branding Colors
UMASS_MAROON = "#881c1c"
UMASS_MAROON_LIGHT = "#a52a2a"
UMASS_MAROON_DARK = "#5e1313"

# Modern Color Palette with Transparency
MODERN_COLORS = [
    "rgba(136, 28, 28, 0.8)",    # Maroon
    "rgba(13, 202, 240, 0.8)",   # Cyan
    "rgba(32, 201, 151, 0.8)",   # Teal
    "rgba(255, 193, 7, 0.8)",    # Yellow
    "rgba(253, 126, 20, 0.8)",   # Orange
    "rgba(111, 66, 193, 0.8)",   # Purple
    "rgba(232, 62, 140, 0.8)",   # Pink
    "rgba(102, 16, 242, 0.8)",   # Indigo
]

DB_COLORS = {
    "Milvus": "#0dcaf0",
    "Weaviate": "#20c997",
    "Elasticsearch": "#fec107",
    "Qdrant": "#fd7e14",
    "Pgvector": "#6f42c1",
    "Pinecone": "#e83e8c",
    "Zilliz": "#6610f2",
}

# Gradient colors for fills
GRADIENT_COLORS = {
    "milvus": ["rgba(13, 202, 240, 0.3)", "rgba(13, 202, 240, 0.8)"],
    "weaviate": ["rgba(32, 201, 151, 0.3)", "rgba(32, 201, 151, 0.8)"],
}


def get_current_theme():
    """
    Detect the current Streamlit theme.
    Returns 'dark' or 'light' based on session state or system preference.
    """
    # Check session state for user preference
    if "app_theme" in st.session_state:
        return st.session_state["app_theme"]
    
    # Try to detect from Streamlit's internal theme config
    try:
        # Streamlit stores theme info in config
        theme_config = st.config.get_option("theme.base")
        if theme_config == "dark":
            return "dark"
        elif theme_config == "light":
            return "light"
    except:
        pass
    
    # Default to dark (based on user's screenshot)
    return "dark"


def set_app_theme(theme: str):
    """Set the app theme in session state."""
    st.session_state["app_theme"] = theme


def get_modern_layout(title: str = "", height: int = 500, theme: str = "light"):
    """
    Get a modern, glassmorphism-style layout configuration for Plotly charts.
    """
    is_dark = theme == "dark"
    
    # Colors based on theme
    text_color = "#fff" if is_dark else "#333"
    grid_color = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.05)"
    paper_bgcolor = "rgba(20, 20, 20, 0.95)" if is_dark else "rgba(255, 255, 255, 0.5)"
    plot_bgcolor = "rgba(30, 30, 30, 0.9)" if is_dark else "rgba(255, 255, 255, 0.7)"
    title_color = UMASS_MAROON_LIGHT if is_dark else UMASS_MAROON
    
    return dict(
        paper_bgcolor=paper_bgcolor,
        plot_bgcolor=plot_bgcolor,
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            color=text_color,
        ),
        title=dict(
            text=title,
            font=dict(size=18, color=title_color, family="Inter, sans-serif"),
            x=0,
        ),
        xaxis=dict(
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            tickfont=dict(color=text_color),
        ),
        yaxis=dict(
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            tickfont=dict(color=text_color),
        ),
        height=height,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            font=dict(color=text_color),
            bgcolor="rgba(0,0,0,0)",
        ),
    )


def get_trace_styling(chart_type: str = "line", theme: str = "light"):
    """
    Get standardized trace styling for different chart types.
    """
    style = {}
    
    if chart_type == "line":
        style = dict(
            line_shape="spline",
            line_width=3,
            marker_size=8,
            marker_line_width=2,
            marker_line_color="white",
            marker_symbol="circle",
        )
    elif chart_type == "bar":
        style = dict(
            marker_line_width=0,
            marker_opacity=0.9,
        )
    elif chart_type in ["box", "violin"]:
        style = dict(
            marker_opacity=0.8,
            line_width=1.5,
        )
        
    return style

CHART_CONTAINER_CSS = """
<style>
.stExpander {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 1rem;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stExpander:hover {
    box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
}

.stPlotlyChart {
    border-radius: 8px;
    overflow: hidden;
    animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
"""
