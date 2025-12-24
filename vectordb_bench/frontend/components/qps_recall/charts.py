from vectordb_bench.frontend.components.check_results.expanderStyle import (
    initMainExpanderStyle,
)
from vectordb_bench.metric import metric_order
import pandas as pd
import plotly.graph_objects as go
from vectordb_bench.frontend.components.chart_theme import (
    get_modern_layout,
    get_current_theme,
    MODERN_COLORS,
)


def drawCharts(st, allData, caseNames: list[str], show_labels: bool = False, comparison_colors: dict = None):
    initMainExpanderStyle(st)
    for caseName in caseNames:
        chartContainer = st.expander(caseName, True)
        data = [data for data in allData if data["case_name"] == caseName]
        drawChart(data, chartContainer, key_prefix=caseName, show_labels=show_labels, comparison_colors=comparison_colors)


def drawChart(data, st, key_prefix: str, show_labels: bool = False, comparison_colors: dict = None):
    metricsSet = set()
    for d in data:
        metricsSet = metricsSet.union(d["metricsSet"])
    showlineMetrics = [metric for metric in metric_order[:2] if metric in metricsSet]

    if showlineMetrics:
        metric = showlineMetrics[0]
        key = f"{key_prefix}-{metric}"
        drawlinechart(st, data, metric, key=key, show_labels=show_labels, comparison_colors=comparison_colors)


def drawBestperformance(data, y, group):
    all_filter_points = []
    data = pd.DataFrame(data)
    grouped = data.groupby(group)
    for name, group_df in grouped:
        filter_points = []
        current_start = 0
        for _ in range(len(group_df)):
            if current_start >= len(group_df):
                break
            max_index = group_df[y].iloc[current_start:].idxmax()
            filter_points.append(group_df.loc[max_index])

            current_start = group_df.index.get_loc(max_index) + 1
        all_filter_points.extend(filter_points)

    all_filter_df = pd.DataFrame(all_filter_points)
    remaining_df = data[~data.isin(all_filter_df).any(axis=1)]
    new_data = all_filter_df.to_dict(orient="records")
    remain_data = remaining_df.to_dict(orient="records")
    return new_data, remain_data


def drawlinechart(st, data: list[object], metric, key: str, show_labels: bool = False, comparison_colors: dict = None):
    minV = min([d.get(metric, 0) for d in data])
    maxV = max([d.get(metric, 0) for d in data])
    padding = maxV - minV
    rangeV = [
        minV - padding * 0.1,
        maxV + padding * 0.1,
    ]
    x = "recall"
    xrange = [0.8, 1.01]
    y = "qps"
    yrange = rangeV
    data.sort(key=lambda a: a[x])
    
    # Extract vendor from db_name for color mapping
    def extract_vendor(db_name):
        db_lower = db_name.lower()
        if "milvus" in db_lower:
            return "milvus"
        elif "weaviate" in db_lower:
            return "weaviate"
        elif "qdrant" in db_lower:
            return "qdrant"
        else:
            return db_name
    
    # Add vendor field to each data point
    for d in data:
        d["vendor"] = extract_vendor(d["db_name"])
    
    # Always group by db_name (individual configs)
    group = "db_name"
    new_data, new_remain_data = drawBestperformance(data, y, group)
    unique_db_names = list(set(item["db_name"] for item in new_data + new_remain_data))

    # Build color map: if comparison mode, map by vendor; otherwise use MODERN_COLORS
    if comparison_colors:
        color_map = {}
        for db_name in unique_db_names:
            vendor = extract_vendor(db_name)
            color_map[db_name] = comparison_colors.get(vendor, "#888")
    else:
        color_map = {
            db: MODERN_COLORS[i % len(MODERN_COLORS)]
            for i, db in enumerate(unique_db_names)
        }

    fig = go.Figure()
    new_data_df = pd.DataFrame(new_data)

    # Plot each individual config as a separate line
    for db_name in unique_db_names:
        db_data = new_data_df[new_data_df["db_name"] == db_name]
        if len(db_data) == 0:
            continue
        mode = "lines+markers+text" if show_labels else "lines+markers"
        fig.add_trace(
            go.Scatter(
                x=db_data["recall"],
                y=db_data["qps"],
                mode=mode,
                name=db_name,
                line=dict(color=color_map[db_name]),
                marker=dict(color=color_map[db_name]),
                showlegend=True,
                hovertemplate="DB: %{fullData.name}<br>QPS=%{y:.4g}, Recall=%{x:.2f}",
                text=[f"{qps:.4g}@{recall:.2f}" for recall, qps in zip(db_data["recall"], db_data["qps"])],
                textposition="top right",
            )
        )

    for item in new_remain_data:
        fig.add_trace(
            go.Scatter(
                x=[item["recall"]],
                y=[item["qps"]],
                mode="markers",
                name=item["db_name"],
                marker=dict(color=color_map.get(item["db_name"], "#888")),
                showlegend=False,
            )
        )
    
    theme = get_current_theme()
    layout_updates = get_modern_layout(height=500, theme=theme)
    
    # Update layout params to avoid duplicate kwargs error
    layout_updates["margin"] = dict(l=0, r=0, t=40, b=0, pad=8)
    layout_updates["legend"] = dict(orientation="h", yanchor="bottom", y=1, xanchor="right", x=1, title="")

    fig.update_xaxes(range=xrange, title_text="Recall")
    fig.update_yaxes(range=yrange, title_text="QPS")
    fig.update_layout(**layout_updates)
    st.plotly_chart(fig, use_container_width=True, key=key)

