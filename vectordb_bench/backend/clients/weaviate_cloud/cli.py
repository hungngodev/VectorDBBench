from typing import Annotated, Unpack

import click
from pydantic import SecretStr

from ..api import MetricType
from ....cli.cli import (
    CommonTypedDict,
    cli,
    click_parameter_decorators_from_typed_dict,
    run,
)
from .. import DB


class WeaviateTypedDict(CommonTypedDict):
    api_key: Annotated[
        str,
        click.option("--api-key", type=str, help="Weaviate api key", required=False, default=""),
    ]
    url: Annotated[
        str,
        click.option("--url", type=str, help="Weaviate url", required=True),
    ]
    no_auth: Annotated[
        bool,
        click.option(
            "--no-auth",
            is_flag=True,
            help="Do not use api-key, set it to true if you are using a local setup. Default is False.",
            default=False,
        ),
    ]
    m: Annotated[
        int,
        click.option("--m", type=int, default=16, help="HNSW index parameter m."),
    ]
    ef_construct: Annotated[
        int,
        click.option("--ef-construction", type=int, default=256, help="HNSW index parameter ef_construction"),
    ]
    ef: Annotated[
        int,
        click.option("--ef", type=int, default=256, help="HNSW index parameter ef for search"),
    ]
    metric_type: Annotated[
        str,
        click.option(
            "--metric-type",
            type=click.Choice([metric.value for metric in (MetricType.COSINE, MetricType.L2, MetricType.IP)], case_sensitive=False),
            default=MetricType.COSINE.value,
            show_default=True,
            help="Distance metric for Weaviate HNSW.",
        ),
    ]


@cli.command()
@click_parameter_decorators_from_typed_dict(WeaviateTypedDict)
def Weaviate(**parameters: Unpack[WeaviateTypedDict]):
    from .config import WeaviateConfig, WeaviateIndexConfig

    run(
        db=DB.WeaviateCloud,
        db_config=WeaviateConfig(
            db_label=parameters["db_label"],
            api_key=SecretStr(parameters["api_key"]) if parameters["api_key"] != "" else SecretStr("-"),
            url=SecretStr(parameters["url"]),
            no_auth=parameters["no_auth"],
        ),
        db_case_config=WeaviateIndexConfig(
            metric_type=MetricType(parameters["metric_type"].upper()),
            efConstruction=parameters["ef_construction"],
            maxConnections=parameters["m"],
            ef=parameters["ef"],
        ),
        **parameters,
    )
