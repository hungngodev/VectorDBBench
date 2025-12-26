import streamlit as st
from vectordb_bench.backend.cases import CaseLabel
from vectordb_bench.backend.filter import FilterOp
from vectordb_bench.frontend.components.check_results.footer import footer
from vectordb_bench.frontend.components.check_results.headerIcon import drawHeaderIcon
from vectordb_bench.frontend.components.check_results.nav import (
    NavToResults,
    NavToRunTest,
    NavToPages,
)
from vectordb_bench.frontend.components.check_results.filters import getshownData
from vectordb_bench.frontend.components.charts.charts import drawChartsByCase
from vectordb_bench.frontend.components.qps_recall.charts import drawCharts as drawQpsRecallCharts
from vectordb_bench.frontend.components.qps_recall.data import getshownData as getQpsRecallData
from vectordb_bench.frontend.components.get_results.saveAsImage import getResults
from vectordb_bench.frontend.config.styles import FAVICON
from vectordb_bench.interface import benchmark_runner
from vectordb_bench.models import TestResult, CaseResult


def main():
    # set page config
    st.set_page_config(
        page_title="VDBBench Charts",
        page_icon=FAVICON,
        layout="wide",
    )

    # header
    drawHeaderIcon(st)

    # navigate
    NavToPages(st)

    allResults = benchmark_runner.get_results()

    st.title("VectorDB Benchmark Charts")

    # Chart type selection - all available chart types
    chart_types = [
        "QPS vs Latency",
        "QPS vs Concurrency", 
        "QPS vs Recall",  # NEW - from qps_recall page
        "Peak QPS Comparison",
        "QPS vs EF Scatter",
        "QPS Distribution (Box)",
        "QPS Distribution (Violin)",
        "Latency Distribution (Violin)",
        "EF vs QPS Heatmap",
    ]
    
    # First row: Chart type and Latency type
    col1, col2 = st.columns([2, 2])
    with col1:
        chart_type = st.selectbox("Chart Type", options=chart_types, index=0)
    with col2:
        if chart_type in ["QPS vs Latency", "Latency Distribution (Violin)"]:
            latency_type = st.selectbox("Latency Type", options=["latency_p99", "latency_p95", "latency_avg"], index=0)
        else:
            latency_type = "latency_p99"  # default

    show_labels = st.checkbox("Show point labels", value=False, help="Show labels on data points")
    compare_mode = st.checkbox("Compare 2 Databases", value=False, help="Group all configs by database vendor (Milvus vs Weaviate)")
    
    default_comparison_colors = {"milvus": "#2E86DE", "weaviate": "#EE5A6F", "qdrant": "#26de81"}

    if chart_type == "QPS vs Recall":
        comparison_colors = default_comparison_colors if compare_mode else None
        # QPS vs Recall uses performance data (not concurrent data)
        resultSelectorContainer = st.sidebar.container()
        
        def case_results_filter(case_result: CaseResult) -> bool:
            case = case_result.task_config.case_config.case
            return case.label == CaseLabel.Performance and case.filters.type == FilterOp.NonFilter
        
        shownData, failedTasks, showCaseNames = getQpsRecallData(
            resultSelectorContainer,
            allResults,
            case_results_filter=case_results_filter,
        )
        
        resultSelectorContainer.divider()
        
        # nav
        navContainer = st.sidebar.container()
        NavToRunTest(navContainer)
        NavToResults(navContainer)
        
        # save or share
        resultsContainer = st.sidebar.container()
        getResults(resultsContainer, "vectordb_bench_charts")
        
        # Draw QPS vs Recall charts
        drawQpsRecallCharts(st, shownData, showCaseNames, show_labels=show_labels, comparison_colors=comparison_colors)
    else:
        comparison_colors = default_comparison_colors if compare_mode else None
        
        def check_conc_data(res: TestResult):
            case_results = res.results
            count = 0
            for case_result in case_results:
                if len(case_result.metrics.conc_num_list) > 0:
                    count += 1
            return count > 0

        checkedResults = [res for res in allResults if check_conc_data(res)]

        # results selector
        resultSelectorContainer = st.sidebar.container()
        shownData, _, showCaseNames = getshownData(resultSelectorContainer, checkedResults)
        
        resultSelectorContainer.divider()

        # nav
        navContainer = st.sidebar.container()
        NavToRunTest(navContainer)
        NavToResults(navContainer)

        # save or share
        resultsContainer = st.sidebar.container()
        getResults(resultsContainer, "vectordb_bench_charts")

        group_by_db = comparison_colors is not None
        drawChartsByCase(shownData, showCaseNames, st.container(), latency_type=latency_type, chart_type=chart_type, show_labels=show_labels, group_by_db=group_by_db)

    # footer
    footer(st.container())


if __name__ == "__main__":
    main()

