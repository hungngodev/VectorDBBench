from pydantic import BaseModel

from ..api import DBCaseConfig, DBConfig, MetricType


class ValdConfig(DBConfig):
    host: str = "vald-gateway.default.svc.cluster.local"
    port: int = 8081
    use_tls: bool = False
    timeout: float = 30.0
    batch_size: int = 64
    grpc_max_message_length: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "host": self.host,
            "port": self.port,
            "use_tls": self.use_tls,
            "timeout": self.timeout,
            "batch_size": self.batch_size,
        }
        if self.grpc_max_message_length is not None:
            payload["grpc_max_message_length"] = self.grpc_max_message_length
        return payload


class ValdIndexConfig(BaseModel, DBCaseConfig):
    metric_type: MetricType = MetricType.COSINE
    num: int = 10
    min_num: int | None = None
    radius: float | None = None
    epsilon: float | None = None
    timeout: float | None = None
    skip_strict_exist_check: bool = True
    wait_for_sync_seconds: float = 5.0

    def index_param(self) -> dict:
        return {}

    def search_param(self) -> dict:
        return {
            "metric_type": self.metric_type,
            "num": self.num,
            "min_num": self.min_num,
            "radius": self.radius,
            "epsilon": self.epsilon,
            "timeout": self.timeout,
        }
