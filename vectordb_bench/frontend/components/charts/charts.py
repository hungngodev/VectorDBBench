from vectordb_bench.frontend.components.check_results.expanderStyle import (
    initMainExpanderStyle,
)
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import re

from vectordb_bench.frontend.config.styles import COLOR_MAP


def parse_db_name(db_name: str) -> dict:
    """Parse db_name like 'milvus-m32-ef100-rep3-shard1' into components."""
    parts = {"db": None, "ef": None, "m": None, "rep": None, "raw": db_name}
    
    if "milvus" in db_name.lower():
        parts["db"] = "milvus"
    elif "weaviate" in db_name.lower():
        parts["db"] = "weaviate"
    elif "qdrant" in db_name.lower():
        parts["db"] = "qdrant"
    
    ef_match = re.search(r'-ef(\d+)', db_name)
    if ef_match:
        parts["ef"] = int(ef_match.group(1))
    
    m_match = re.search(r'-m(\d+)', db_name)
    if m_match:
        parts["m"] = int(m_match.group(1))
    
    rep_match = re.search(r'-rep(\d+)', db_name)
    if rep_match:
        parts["rep"] = int(rep_match.group(1))
    
    return parts


def drawChartsByCase(allData, showCaseNames: list[str], st, latency_type: str, chart_type: str = "QPS vs Latency", show_labels: bool = False, group_by_db: bool = False):
    initMainExpanderStyle(st)
    for caseName in showCaseNames:
        chartContainer = st.expander(caseName, True)
        caseDataList = [data for data in allData if data["case_name"] == caseName]
        data = [
            {
                "conc_num": caseData["conc_num_list"][i],
                "qps": (caseData["conc_qps_list"][i] if 0 <= i < len(caseData["conc_qps_list"]) else 0),
                "latency_p99": (
                    caseData["conc_latency_p99_list"][i] * 1000
                    if 0 <= i < len(caseData["conc_latency_p99_list"])
                    else 0
                ),
                "latency_p95": (
                    caseData["conc_latency_p95_list"][i] * 1000
                    if "conc_latency_p95_list" in caseData and 0 <= i < len(caseData["conc_latency_p95_list"])
                    else 0
                ),
                "latency_avg": (
                    caseData["conc_latency_avg_list"][i] * 1000
                    if 0 <= i < len(caseData["conc_latency_avg_list"])
                    else 0
                ),
                "db_name": caseData["db_name"],
                "db": caseData["db"],
            }
            for caseData in caseDataList
            for i in range(len(caseData["conc_num_list"]))
        ]
        
        comparison_colors = None
        if group_by_db:
            comparison_colors = {"milvus": "#2E86DE", "weaviate": "#EE5A6F"}
        
        if chart_type == "QPS vs Concurrency":
            drawChart(data, chartContainer, key=f"{caseName}-qps-conc", x_metric="conc_num", y_metric="qps", show_labels=show_labels, comparison_colors=comparison_colors)
        elif chart_type == "QPS Distribution (Box)":
            drawBoxPlot(data, chartContainer, key=f"{caseName}-box", metric="qps", group_by_db=group_by_db)
        elif chart_type == "QPS Distribution (Violin)":
            drawViolinPlot(data, chartContainer, key=f"{caseName}-violin", metric="qps", group_by_db=group_by_db)
        elif chart_type == "Latency Distribution (Violin)":
            drawViolinPlot(data, chartContainer, key=f"{caseName}-violin-lat", metric=latency_type, group_by_db=group_by_db)
        elif chart_type == "EF vs QPS Heatmap":
            drawHeatmap(data, chartContainer, key=f"{caseName}-heatmap", group_by_db=group_by_db)
        elif chart_type == "Peak QPS Comparison":
            drawGroupedBar(data, chartContainer, key=f"{caseName}-grouped-bar", group_by_db=group_by_db)
        elif chart_type == "QPS vs EF Scatter":
            drawScatterWithTrend(data, chartContainer, key=f"{caseName}-scatter", group_by_db=group_by_db)
        else:
            drawChart(data, chartContainer, key=f"{caseName}-qps-p99", x_metric=latency_type, y_metric="qps", show_labels=show_labels, comparison_colors=comparison_colors)


def getRange(metric, data, padding_multipliers):
    values = [d.get(metric, 0) for d in data if d.get(metric, 0) > 0]
    if not values:
        return [0, 1]
    minV = min(values)
    maxV = max(values)
    padding = maxV - minV if maxV > minV else maxV * 0.1
    rangeV = [
        max(0, minV - padding * padding_multipliers[0]),
        maxV + padding * padding_multipliers[1],
    ]
    return rangeV


def gen_title(s: str) -> str:
    if "latency" in s:
        return f'{s.replace("_", " ").title()} (ms)'
    elif s == "conc_num":
        return "Concurrency Level"
    elif s == "ef":
        return "EF Search Value"
    else:
        return s.upper()


def drawChart(data, st, key: str, x_metric: str = "latency_p99", y_metric: str = "qps", show_labels: bool = False, comparison_colors: dict = None):
    if len(data) == 0:
        return

    x = x_metric
    xrange = getRange(x, data, [0.05, 0.1])

    y = y_metric
    yrange = getRange(y, data, [0.2, 0.1])

    color = "db_name"
    if comparison_colors:
        color_discrete_map = {}
        for d in data:
            parsed = parse_db_name(d["db_name"])
            vendor = parsed.get("db", "").lower()
            if vendor in comparison_colors:
                color_discrete_map[d["db_name"]] = comparison_colors[vendor]
    else:
        color_discrete_map = None
    
    line_group = "db_name"
    text = "conc_num" if show_labels else None

    data.sort(key=lambda a: a["conc_num"])

    fig = px.line(
        data,
        x=x,
        y=y,
        color=color,
        color_discrete_map=color_discrete_map,
        line_group=line_group,
        text=text,
        markers=True,
        hover_data={
            "conc_num": True,
            "db_name": True,
        },
        height=720,
    )
    fig.update_xaxes(range=xrange, title_text=gen_title(x_metric))
    fig.update_yaxes(range=yrange, title_text=gen_title(y_metric))
    if show_labels:
        fig.update_traces(textposition="bottom right", texttemplate="conc-%{text:,.4~r}")

    st.plotly_chart(fig, use_container_width=True, key=key)


def drawBoxPlot(data, st, key: str, metric: str = "qps", comparison_colors: dict = None):
    """Draw a box plot showing distribution of a metric across databases."""
    if len(data) == 0:
        return
    
    # Add parsed info and ensure lowercase database names
    for d in data:
        parsed = parse_db_name(d["db_name"])
        d["database"] = (parsed["db"] or d.get("db", "")).lower()  # Ensure lowercase
        d["ef"] = parsed["ef"]
    
    df = pd.DataFrame(data)
    
    # Always color by database vendor
    color_col = "database"
    
    # Build color map
    if comparison_colors:
        # Explicitly map each unique database to comparison color
        unique_dbs = df["database"].unique()
        color_map = {}
        for db in unique_dbs:
            db_lower = str(db).lower()
            if db_lower in comparison_colors:
                color_map[db] = comparison_colors[db_lower]
    else:
        color_map = None
    
    fig = px.box(
        df,
        x="database",
        y=metric,
        color=color_col,
        color_discrete_map=color_map,  # Use explicitly built color map
        points="all",
        hover_data=["db_name", "conc_num"],
        height=500,
        title=f"{gen_title(metric)} Distribution by Database",
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
        showlegend=comparison_colors is not None,  # Show legend in comparison mode
        xaxis_title="Database",
        yaxis_title=gen_title(metric),
    )
    
    st.plotly_chart(fig, use_container_width=True, key=key)


def drawViolinPlot(data, st, key: str, metric: str = "qps", comparison_colors: dict = None):
    """Draw a violin plot showing full distribution shape across databases."""
    if len(data) == 0:
        return
    
    # Add parsed info and ensure lowercase database names
    for d in data:
        parsed = parse_db_name(d["db_name"])
        d["database"] = (parsed["db"] or d.get("db", "")).lower()  # Ensure lowercase
    
    df = pd.DataFrame(data)
    
    # Always color by database vendor
    color_col = "database"
    
    # Build color map
    if comparison_colors:
        # Explicitly map each unique database to comparison color
        unique_dbs = df["database"].unique()
        color_map = {}
        for db in unique_dbs:
            db_lower = str(db).lower()
            if db_lower in comparison_colors:
                color_map[db] = comparison_colors[db_lower]
    else:
        color_map = None
    
    fig = px.violin(
        df,
        x="database",
        y=metric,
        color=color_col,
        color_discrete_map=color_map,  # Use explicitly built color map
        box=True,
        points="all",
        hover_data=["db_name", "conc_num"],
        height=500,
        title=f"{gen_title(metric)} Distribution (Violin)",
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
        showlegend=comparison_colors is not None,
        xaxis_title="Database",
        yaxis_title=gen_title(metric),
    )
    
    st.plotly_chart(fig, use_container_width=True, key=key)


def drawHeatmap(data, st, key: str, comparison_colors: dict = None):
    """Draw a heatmap showing QPS across EF values and databases."""
    if len(data) == 0:
        return
    
    # Parse EF values from db_name
    for d in data:
        parsed = parse_db_name(d["db_name"])
        d["ef"] = parsed["ef"]
        d["database"] = parsed["db"] or d["db"]
    
    # Filter to only data with EF values
    data_with_ef = [d for d in data if d["ef"] is not None]
    if not data_with_ef:
        st.warning("No EF values found in data for heatmap.")
        return
    
    df = pd.DataFrame(data_with_ef)
    
    # Get max QPS for each database-EF combination (across all concurrency levels)
    pivot_df = df.pivot_table(
        values="qps",
        index="database",
        columns="ef",
        aggfunc="max"
    )
    
    fig = px.imshow(
        pivot_df,
        labels=dict(x="EF Search Value", y="Database", color="Max QPS"),
        aspect="auto",
        color_continuous_scale="Viridis",
        height=400,
        title="Peak QPS Heatmap (EF vs Database)",
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
    )
    
    # Add text annotations
    fig.update_traces(
        text=pivot_df.values.round(0).astype(int),
        texttemplate="%{text}",
        textfont={"size": 10},
    )
    
    st.plotly_chart(fig, use_container_width=True, key=key)


def drawScatterWithTrend(data, st, key: str, comparison_colors: dict = None):
    """Draw scatter plot of QPS vs EF with trend lines per database."""
    if len(data) == 0:
        return
    
    # Parse EF values
    for d in data:
        parsed = parse_db_name(d["db_name"])
        d["ef"] = parsed["ef"]
        d["database"] = parsed["db"] or d["db"]
    
    # Filter to only data with EF values
    data_with_ef = [d for d in data if d["ef"] is not None]
    if not data_with_ef:
        st.warning("No EF values found in data for scatter plot.")
        return
    
    df = pd.DataFrame(data_with_ef)
    
    # Get peak QPS per EF-database combo
    # In comparison mode, group by vendor
    group_col = "database" if comparison_colors else "database"
    peak_df = df.groupby([group_col, "ef"]).agg({"qps": "max"}).reset_index()
    
    color_col = "database" if comparison_colors else "database"
    
    fig = px.scatter(
        peak_df,
        x="ef",
        y="qps",
        color=color_col,
        color_discrete_map=comparison_colors,
        trendline="lowess",
        height=500,
        title="Peak QPS vs EF Search Value (with trend)",
        labels={"ef": "EF Search Value", "qps": "Peak QPS"},
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    st.plotly_chart(fig, use_container_width=True, key=key)


def drawGroupedBar(data, st, key: str, comparison_colors: dict = None):
    """Draw grouped bar chart comparing peak QPS across databases."""
    if len(data) == 0:
        return
    
    # Parse database info
    for d in data:
        parsed = parse_db_name(d["db_name"])
        d["database"] = parsed["db"] or d["db"]
        d["ef"] = parsed["ef"]
    
    df = pd.DataFrame(data)
    
    # Get top 5 configs per database by max QPS
    top_configs = []
    group_col = "database" if comparison_colors else "database"
    for db in df[group_col].unique():
        db_df = df[df[group_col] == db]
        peak_per_config = db_df.groupby("db_name").agg({"qps": "max"}).reset_index()
        top_5 = peak_per_config.nlargest(5, "qps")
        for _, row in top_5.iterrows():
            top_configs.append({
                "db_name": row["db_name"],
                "database": db,
                "peak_qps": row["qps"],
            })
    
    top_df = pd.DataFrame(top_configs)
    
    # Don't shorten - use full db_name to ensure uniqueness
    # Each config will get its own bar
    
    color_col = "database" if comparison_colors else "database"
    
    fig = px.bar(
        top_df,
        x="db_name",  # Use full name to ensure uniqueness
        y="peak_qps",
        color=color_col,
        color_discrete_map=comparison_colors,
        height=600,
        title="Top 5 Configurations per Database (Peak QPS)",
        labels={"db_name": "Configuration", "peak_qps": "Peak QPS"},
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=200),  # Much larger bottom margin
        xaxis_tickangle=-45,
        xaxis=dict(
            tickmode='linear',
            automargin=True  # Auto-adjust margin for labels
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        showlegend=True,
    )
    
    # Add vertical line separator between database groups
    # Find where Weaviate ends and Milvus begins
    databases = top_df["database"].tolist()
    if len(databases) > 1 and databases[0] != databases[-1]:
        # Find the transition point
        for i in range(len(databases) - 1):
            if databases[i] != databases[i + 1]:
                # Add vertical line between position i and i+1
                fig.add_vline(
                    x=i + 0.5,
                    line_width=2,
                    line_dash="dash",
                    line_color="gray",
                    opacity=0.7
                )
                break
    
    st.plotly_chart(fig, use_container_width=True, key=key)

