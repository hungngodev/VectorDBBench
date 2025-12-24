from vectordb_bench.backend.cases import Case
from vectordb_bench.backend.dataset import DatasetWithSizeType
from vectordb_bench.backend.filter import FilterOp
from vectordb_bench.frontend.components.check_results.data import getChartData
from vectordb_bench.frontend.components.check_results.expanderStyle import (
    initSidebarExanderStyle,
)
from vectordb_bench.frontend.config.dbCaseConfigs import CASE_NAME_ORDER
from vectordb_bench.frontend.config.styles import SIDEBAR_CONTROL_COLUMNS
import streamlit as st
from typing import Callable
import re
from collections import defaultdict

from vectordb_bench.models import CaseResult, TestResult


def parse_task_label(label: str) -> dict:
    """Parse task label like 'DISTRIBUTED-1M-milvus-m32-ef100-rep3-shard1' into components."""
    parts = {
        "batch": None,
        "db": None,
        "m": None,
        "ef": None,
        "rep": None,
        "shard": None,
        "raw": label,
    }
    
    batch_match = re.match(r'^([A-Z0-9-]+?)(?:-(?:milvus|weaviate|qdrant|vald))', label, re.IGNORECASE)
    if batch_match:
        parts["batch"] = batch_match.group(1)
    
    for db in ["milvus", "weaviate", "qdrant", "vald"]:
        if db in label.lower():
            parts["db"] = db
            break
    
    for param in ["m", "ef", "rep", "shard"]:
        match = re.search(rf'-{param}(\d+)', label)
        if match:
            parts[param] = int(match.group(1))
    
    return parts


def get_ef_range(ef: int) -> str:
    """Categorize EF value into ranges."""
    if ef is None:
        return "Unknown"
    elif ef <= 150:
        return "Low (≤150)"
    elif ef <= 300:
        return "Medium (151-300)"
    elif ef <= 600:
        return "High (301-600)"
    else:
        return "Very High (>600)"


def getshownData(st, results: list[TestResult], filter_type: FilterOp = FilterOp.NonFilter, **kwargs):
    st.markdown(
        """<style>
        div[data-testid='stSidebarNav'] {display: none;}
        
        /* Expand sidebar width when open */
        section[data-testid="stSidebar"][aria-expanded="true"] {
            width: 450px !important;
            min-width: 450px !important;
        }
        section[data-testid="stSidebar"][aria-expanded="true"] > div {
            width: 450px !important;
        }
        
        /* Fully collapse sidebar when closed */
        section[data-testid="stSidebar"][aria-expanded="false"] {
            width: 0px !important;
            min-width: 0px !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] > div {
            width: 0px !important;
            display: none !important;
        }
        
        /* Make multiselect chips wrap and show full text */
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            max-width: 100% !important;
            white-space: normal !important;
            height: auto !important;
            padding: 4px 8px !important;
        }
        
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            word-break: break-word !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.header("Filters")

    shownResults = getshownResults(st, results, **kwargs)
    showDBNames, showCaseNames = getShowDbsAndCases(st, shownResults, filter_type)

    shownData, failedTasks = getChartData(shownResults, showDBNames, showCaseNames)

    return shownData, failedTasks, showCaseNames


def getshownResults(
    sidebar,
    results: list[TestResult],
    case_results_filter: Callable[[CaseResult], bool] = lambda x: True,
    default_selected_task_labels: list[str] = [],
    **kwargs,
) -> list[CaseResult]:
    resultSelectOptions = [
        result.task_label if result.task_label != result.run_id else f"res-{result.run_id[:4]}" for result in results
    ]
    if len(resultSelectOptions) == 0:
        sidebar.write("There are no results to display. Please wait for the task to complete or run a new task.")
        return []

    parsed_labels = {label: parse_task_label(label) for label in resultSelectOptions}
    
    batches = sorted(set(p["batch"] for p in parsed_labels.values() if p["batch"]))
    dbs = sorted(set(p["db"] for p in parsed_labels.values() if p["db"]))
    ef_ranges = sorted(set(get_ef_range(p["ef"]) for p in parsed_labels.values() if p["ef"]))
    
    for filter_name, filter_values in [("batch", batches), ("db", dbs), ("ef_range", ef_ranges)]:
        state_key = f"{filter_name}_filter_state"
        if state_key not in st.session_state:
            st.session_state[state_key] = filter_values.copy()
    
    with sidebar.expander("Quick Filters", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            if len(batches) > 1:
                current_batch_state = [b for b in st.session_state.get("batch_filter_state", batches) if b in batches]
                selected_batches = st.multiselect(
                    "Batch",
                    batches,
                    default=current_batch_state or batches,
                    key="batch_filter_widget"
                )
                st.session_state["batch_filter_state"] = selected_batches
            else:
                selected_batches = batches
        
        with col2:
            if len(dbs) > 1:
                current_db_state = [d for d in st.session_state.get("db_filter_state", dbs) if d in dbs]
                selected_dbs = st.multiselect(
                    "Fine-tune",
                    dbs,
                    default=current_db_state or dbs,
                    key="db_filter_widget"
                )
                st.session_state["db_filter_state"] = selected_dbs
            else:
                selected_dbs = dbs
            
            if len(ef_ranges) > 1:
                current_ef_state = [e for e in st.session_state.get("ef_range_filter_state", ef_ranges) if e in ef_ranges]
                selected_ef_ranges = st.multiselect(
                    "EF Range",
                    ef_ranges,
                    default=current_ef_state or ef_ranges,
                    key="ef_range_filter_widget"
                )
                st.session_state["ef_range_filter_state"] = selected_ef_ranges
            else:
                selected_ef_ranges = ef_ranges
    
    filtered_options = []
    for label in resultSelectOptions:
        p = parsed_labels[label]
        
        if selected_batches and p["batch"] and p["batch"] not in selected_batches:
            continue
        
        if selected_dbs and p["db"] and p["db"] not in selected_dbs:
            continue
        
        if selected_ef_ranges and p["ef"]:
            ef_range = get_ef_range(p["ef"])
            if ef_range not in selected_ef_ranges:
                continue
        
        filtered_options.append(label)
    
    sidebar.caption(f"Showing {len(filtered_options)} of {len(resultSelectOptions)} results")
    
    selectedResult: list[CaseResult] = []
    for option in filtered_options:
        if option in resultSelectOptions:
            case_results = results[resultSelectOptions.index(option)].results
            selectedResult += [r for r in case_results if case_results_filter(r)]

    return selectedResult


def getShowDbsAndCases(sidebar, result: list[CaseResult], filter_type: FilterOp) -> tuple[list[str], list[str]]:
    initSidebarExanderStyle(st)
    case_results = [res for res in result if res.task_config.case_config.case.filters.type == filter_type]
    allDbNames = list(set({res.task_config.db_name for res in case_results}))
    allDbNames.sort()
    allCases: list[Case] = [res.task_config.case_config.case for res in case_results]

    dbFilterContainer = sidebar.container()
    showDBNames = filterView(
        dbFilterContainer,
        "Fine-tune Selection",
        allDbNames,
        col=1,
    )
    showCaseNames = []

    if filter_type == FilterOp.NonFilter:
        allCaseNameSet = set({case.name for case in allCases})
        allCaseNames = [case_name for case_name in CASE_NAME_ORDER if case_name in allCaseNameSet] + [
            case_name for case_name in allCaseNameSet if case_name not in CASE_NAME_ORDER
        ]

        caseFilterContainer = sidebar.container()
        showCaseNames = filterView(
            caseFilterContainer,
            "Case Filter",
            [caseName for caseName in allCaseNames],
            col=1,
        )

    if filter_type == FilterOp.StrEqual or filter_type == FilterOp.NumGE:
        container = sidebar.container()
        datasetWithSizeTypes = [dataset_with_size_type for dataset_with_size_type in DatasetWithSizeType]
        showDatasetWithSizeTypes = filterView(
            container,
            "Case Filter",
            datasetWithSizeTypes,
            col=1,
            optionLables=[v.value for v in datasetWithSizeTypes],
        )
        datasets = [dataset_with_size_type.get_manager() for dataset_with_size_type in showDatasetWithSizeTypes]
        showCaseNames = list(set([case.name for case in allCases if case.dataset in datasets]))

    return showDBNames, showCaseNames


def filterView(container, header, options, col, optionLables=None):
    selectAllState = f"{header}-select-all-state"
    if selectAllState not in st.session_state:
        st.session_state[selectAllState] = True

    countKeyState = f"{header}-select-all-count-key"
    if countKeyState not in st.session_state:
        st.session_state[countKeyState] = 0

    expander = container.expander(header, True)
    selectAllColumns = expander.columns(SIDEBAR_CONTROL_COLUMNS, gap="small")
    selectAllButton = selectAllColumns[SIDEBAR_CONTROL_COLUMNS - 2].button(
        "select all",
        key=f"{header}-select-all-button",
        # type="primary",
    )
    clearAllButton = selectAllColumns[SIDEBAR_CONTROL_COLUMNS - 1].button(
        "clear all",
        key=f"{header}-clear-all-button",
        # type="primary",
    )
    if selectAllButton:
        st.session_state[selectAllState] = True
        st.session_state[countKeyState] += 1
    if clearAllButton:
        st.session_state[selectAllState] = False
        st.session_state[countKeyState] += 1
    columns = expander.columns(
        col,
        gap="small",
    )
    if optionLables is None:
        optionLables = options
    isActive = {option: st.session_state[selectAllState] for option in optionLables}
    for i, option in enumerate(optionLables):
        isActive[option] = columns[i % col].checkbox(
            optionLables[i],
            value=isActive[option],
            key=f"{optionLables[i]}-{st.session_state[countKeyState]}",
        )

    return [options[i] for i, option in enumerate(optionLables) if isActive[option]]

