from typing import Annotated, Unpack

import click

from vectordb_bench.backend.clients import DB
from vectordb_bench.backend.clients.api import MetricType
from vectordb_bench.cli.cli import (
    CommonTypedDict,
    cli,
    click_parameter_decorators_from_typed_dict,
    run,
)

DBTYPE = DB.Vald

_METRIC_CHOICES = [metric.value for metric in (MetricType.L2, MetricType.COSINE, MetricType.IP)]


class ValdTypedDict(CommonTypedDict):
    host: Annotated[
        str,
        click.option(
            "--host",
            type=str,
            default="vald-gateway.default.svc.cluster.local",
            show_default=True,
            help="Host name or IP for the Vald gateway service.",
        ),
    ]
    port: Annotated[
        int,
        click.option("--port", type=int, default=8081, show_default=True, help="Port exposed by the Vald gateway."),
    ]
    use_tls: Annotated[
        bool,
        click.option(
            "--use-tls",
            type=bool,
            default=False,
            show_default=True,
            help="Enable TLS when connecting to the Vald gateway.",
        ),
    ]
    timeout: Annotated[
        float,
        click.option(
            "--timeout",
            type=float,
            default=30.0,
            show_default=True,
            help="Timeout (seconds) for gRPC operations.",
        ),
    ]
    batch_size: Annotated[
        int,
        click.option(
            "--batch-size",
            type=int,
            default=64,
            show_default=True,
            help="Number of vectors per MultiInsert request.",
        ),
    ]
    metric_type: Annotated[
        str,
        click.option(
            "--metric-type",
            type=click.Choice(_METRIC_CHOICES, case_sensitive=False),
            default=MetricType.COSINE.value,
            show_default=True,
            help="Similarity metric to use for Vald searches.",
        ),
    ]
    num: Annotated[
        int,
        click.option("--num", type=int, default=10, show_default=True, help="Target number of neighbors to retrieve."),
    ]
    min_num: Annotated[
        int | None,
        click.option(
            "--min-num",
            type=int,
            default=None,
            show_default=True,
            help="Minimum number of neighbors to return (Vald search config).",
        ),
    ]
    radius: Annotated[
        float | None,
        click.option(
            "--radius",
            type=float,
            default=None,
            show_default=True,
            help="Search radius when using Vald range search tuning.",
        ),
    ]
    epsilon: Annotated[
        float | None,
        click.option(
            "--epsilon",
            type=float,
            default=None,
            show_default=True,
            help="Epsilon value for Vald approximate search.",
        ),
    ]
    wait_for_sync_seconds: Annotated[
        float,
        click.option(
            "--wait-for-sync-seconds",
            type=float,
            default=5.0,
            show_default=True,
            help="Additional wait after insertions to let Vald index synchronize.",
        ),
    ]
    skip_strict_exist_check: Annotated[
        bool,
        click.option(
            "--skip-strict-exist-check/--no-skip-strict-exist-check",
            default=True,
            show_default=True,
            help="Control Vald's strict existence check during inserts.",
        ),
    ]


@cli.command()
@click_parameter_decorators_from_typed_dict(ValdTypedDict)
def Vald(**parameters: Unpack[ValdTypedDict]):
    from .config import ValdConfig, ValdIndexConfig

    run(
        db=DBTYPE,
        db_config=ValdConfig(
            host=parameters["host"],
            port=parameters["port"],
            use_tls=parameters["use_tls"],
            timeout=parameters["timeout"],
            batch_size=parameters["batch_size"],
        ),
        db_case_config=ValdIndexConfig(
            metric_type=MetricType(parameters["metric_type"].upper()),
            num=parameters["num"],
            min_num=parameters["min_num"],
            radius=parameters["radius"],
            epsilon=parameters["epsilon"],
            timeout=parameters["timeout"],
            skip_strict_exist_check=parameters["skip_strict_exist_check"],
            wait_for_sync_seconds=parameters["wait_for_sync_seconds"],
        ),
        **parameters,
    )
