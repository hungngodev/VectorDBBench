"""Wrapper around the Vald vector database for VectorDBBench."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

import grpc

from ..api import MetricType, VectorDB
from .config import ValdConfig, ValdIndexConfig

log = logging.getLogger(__name__)


class ValdLocal(VectorDB):
    """Vald adapter that satisfies the VectorDBBench client contract."""

    def __init__(
        self,
        dim: int,
        db_config: dict,
        db_case_config: ValdIndexConfig,
        collection_name: str = "VectorDBBenchCollection",
        drop_old: bool = False,
        name: str = "Vald",
        **kwargs: Any,
    ) -> None:
        self.dim = dim
        self.name = name
        self.collection_name = collection_name
        self.config = ValdConfig(**db_config)
        self.case_config = db_case_config

        self._channel: grpc.Channel | None = None
        self._insert_stub = None
        self._search_stub = None
        self._remove_stub = None

        if drop_old:
            log.info("%s does not expose a collection drop API; existing data might be reused.", self.name)

    @contextmanager
    def init(self) -> None:
        """Open gRPC stubs for insertion and search."""
        from vald.v1.vald import insert_pb2_grpc, remove_pb2_grpc, search_pb2_grpc

        endpoint = f"{self.config.host}:{self.config.port}"
        options = []
        if self.config.grpc_max_message_length:
            length = self.config.grpc_max_message_length
            options = [
                ("grpc.max_send_message_length", length),
                ("grpc.max_receive_message_length", length),
            ]

        if self.config.use_tls:
            credentials = grpc.ssl_channel_credentials()
            channel = grpc.secure_channel(endpoint, credentials, options=options)
        else:
            channel = grpc.insecure_channel(endpoint, options=options)

        self._channel = channel
        self._insert_stub = insert_pb2_grpc.InsertStub(channel)
        self._search_stub = search_pb2_grpc.SearchStub(channel)
        self._remove_stub = remove_pb2_grpc.RemoveStub(channel)
        try:
            yield
        finally:
            channel.close()
            self._channel = None
            self._insert_stub = None
            self._search_stub = None
            self._remove_stub = None

    def optimize(self, data_size: int | None = None) -> None:
        """Vald builds its index asynchronously; wait for the configured duration."""
        wait_seconds = max(self.case_config.wait_for_sync_seconds, 0.0)
        if wait_seconds:
            log.info("Waiting %.2f seconds for Vald to synchronize indices.", wait_seconds)
            time.sleep(wait_seconds)

    def insert_embeddings(
        self,
        embeddings: Iterable[list[float]],
        metadata: list[int],
        **kwargs: Any,
    ) -> tuple[int, Exception | None]:
        from grpc import RpcError
        from vald.v1.payload import payload_pb2

        assert self._insert_stub is not None, "Call self.init() before inserting embeddings."
        vectors = list(embeddings)
        if len(vectors) != len(metadata):
            raise ValueError("Length mismatch between embeddings and metadata for Vald insert.")

        batch_size = max(self.config.batch_size, 1)
        inserted = 0
        error: Exception | None = None
        insert_config = payload_pb2.Insert.Config(skip_strict_exist_check=self.case_config.skip_strict_exist_check)
        batch: list[payload_pb2.Insert.Request] = []

        try:
            for vector, meta in zip(vectors, metadata):
                vector_msg = payload_pb2.Object.Vector(id=str(meta), vector=[float(x) for x in vector])
                batch.append(payload_pb2.Insert.Request(vector=vector_msg, config=insert_config))
                if len(batch) >= batch_size:
                    self._multi_insert(batch)
                    inserted += len(batch)
                    batch = []

            if batch:
                self._multi_insert(batch)
                inserted += len(batch)

        except RpcError as exc:  # pragma: no cover - network failure path
            log.warning("Vald insert failed: %s", exc)
            error = exc
        except Exception as exc:  # pragma: no cover - unexpected failure path
            log.warning("Unexpected Vald insert error: %s", exc)
            error = exc

        return inserted, error

    def search_embedding(
        self,
        query: list[float],
        k: int = 100,
        filters: dict | None = None,
        timeout: int | None = None,
    ) -> list[int]:
        from grpc import RpcError
        from vald.v1.payload import payload_pb2

        assert self._search_stub is not None, "Call self.init() before searching."

        params = self.case_config.search_param()
        num = max(params.get("num", k), k)
        search_config = payload_pb2.Search.Config(num=num)

        if params.get("min_num") is not None:
            search_config.min_num = params["min_num"]
        if params.get("radius") is not None:
            search_config.radius = params["radius"]
        if params.get("epsilon") is not None:
            search_config.epsilon = params["epsilon"]

        search_timeout = params.get("timeout", timeout if timeout is not None else self.config.timeout)
        rpc_timeout = self.config.timeout
        if search_timeout is not None:
            search_config.timeout = int(search_timeout)
            rpc_timeout = search_timeout

        attempts = 3
        last_error: Exception | None = None
        for i in range(attempts):
            try:
                response = self._search_stub.Search(
                    payload_pb2.Search.Request(vector=[float(x) for x in query], config=search_config),
                    timeout=rpc_timeout,
                )
                break
            except RpcError as exc:  # pragma: no cover - network failure path
                last_error = exc
                log.warning("Vald search failed (attempt %d/%d): %s", i + 1, attempts, exc)
                time.sleep(0.1)
            except Exception as exc:  # pragma: no cover - unexpected failure path
                last_error = exc
                log.warning("Unexpected Vald search error (attempt %d/%d): %s", i + 1, attempts, exc)
                time.sleep(0.1)
        else:
            # No successful attempts; fail quietly to avoid crashing the runner.
            log.warning("Vald search giving up after %d attempts: %s", attempts, last_error)
            return []

        hits: list[int] = []
        for result in response.results:
            identifier = result.id
            try:
                hits.append(int(identifier))
            except ValueError:
                hits.append(abs(hash(identifier)))
        return hits[:k]

    def need_normalize_cosine(self) -> bool:
        return self.case_config.metric_type == MetricType.COSINE

    def _multi_insert(self, requests: list) -> None:
        from vald.v1.payload import payload_pb2

        assert self._insert_stub is not None
        multi_request = payload_pb2.Insert.MultiRequest(requests=requests)
        self._insert_stub.MultiInsert(multi_request, timeout=self.config.timeout)
