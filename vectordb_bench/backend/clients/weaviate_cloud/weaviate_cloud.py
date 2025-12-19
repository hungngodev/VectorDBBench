"""Wrapper around the Weaviate vector database over VectorDB"""

import logging
from collections.abc import Iterable
from contextlib import contextmanager

import weaviate
from weaviate.exceptions import WeaviateBaseError

from ..api import DBCaseConfig, VectorDB

log = logging.getLogger(__name__)


class WeaviateCloud(VectorDB):
    def __init__(
        self,
        dim: int,
        db_config: dict,
        db_case_config: DBCaseConfig,
        collection_name: str = "VectorDBBenchCollection",
        drop_old: bool = False,
        **kwargs,
    ):
        """Initialize wrapper around the weaviate vector database."""
        db_config.update(
            {
                "auth_client_secret": weaviate.AuthApiKey(
                    api_key=db_config.get("auth_client_secret"),
                ),
            },
        )
        self.db_config = db_config
        self.case_config = db_case_config
        self.collection_name = collection_name

        self._scalar_field = "key"
        self._vector_field = "vector"
        self._index_name = "vector_idx"

        if db_config["no_auth"]:
            del db_config["auth_client_secret"]
        del db_config["no_auth"]

        from weaviate import Client

        client = Client(**db_config)
        if drop_old:
            try:
                if client.schema.exists(self.collection_name):
                    log.info(f"weaviate client drop_old collection: {self.collection_name}")
                    client.schema.delete_class(self.collection_name)
            except WeaviateBaseError as e:
                log.warning(f"Failed to drop collection: {self.collection_name} error: {e!s}")
                raise e from None
        self._create_collection(client)
        client = None

    @contextmanager
    def init(self) -> None:
        """
        Examples:
            >>> with self.init():
            >>>     self.insert_embeddings()
            >>>     self.search_embedding()
        """
        from weaviate import Client

        self.client = Client(**self.db_config)
        yield
        self.client = None
        del self.client

    def optimize(self, data_size: int | None = None):
        assert self.client.schema.exists(self.collection_name)
        self.client.schema.update_config(
            self.collection_name,
            {"vectorIndexConfig": self.case_config.search_param()},
        )

    def _create_collection(self, client: weaviate.Client) -> None:
        if not client.schema.exists(self.collection_name):
            log.info(f"Create collection: {self.collection_name}")
            class_obj = {
                "class": self.collection_name,
                "vectorizer": "none",
                "properties": [
                    {
                        "dataType": ["int"],
                        "name": self._scalar_field,
                    },
                ],
            }
            class_obj["vectorIndexConfig"] = self.case_config.index_param()
            
            # Sharding config for parallel query execution
            sharding_config = self.case_config.sharding_param()
            if sharding_config:
                class_obj["shardingConfig"] = sharding_config
                log.info(f"Creating collection with shardingConfig: {sharding_config}")
            
            # Replication config for fault tolerance
            replication_config = self.case_config.replication_param()
            if replication_config:
                class_obj["replicationConfig"] = replication_config
                log.info(f"Creating collection with replicationConfig: {replication_config}")
            
            try:
                client.schema.create_class(class_obj)
                
                # Wait for shards to be ready when sharding is enabled
                if sharding_config:
                    import time
                    log.info("Waiting for shards to be ready...")
                    for attempt in range(30):  # Wait up to 30 seconds
                        time.sleep(1)
                        try:
                            # Try a simple query to check if shards are ready
                            test_query = client.query.get(self.collection_name, [self._scalar_field]).with_limit(1).do()
                            if "data" in test_query:
                                log.info(f"Shards ready after {attempt + 1} seconds")
                                break
                        except Exception:
                            pass
                    else:
                        log.warning("Shards may not be fully ready after 30 seconds")
                        
            except WeaviateBaseError as e:
                log.warning(f"Failed to create collection: {self.collection_name} error: {e!s}")
                raise e from None

    def insert_embeddings(
        self,
        embeddings: Iterable[list[float]],
        metadata: list[int],
        **kwargs,
    ) -> tuple[int, Exception]:
        """Insert embeddings into Weaviate"""
        assert self.client.schema.exists(self.collection_name)
        insert_count = 0
        try:
            with self.client.batch as batch:
                batch.batch_size = len(metadata)
                batch.dynamic = True
                res = []
                for i in range(len(metadata)):
                    res.append(
                        batch.add_data_object(
                            {self._scalar_field: metadata[i]},
                            class_name=self.collection_name,
                            vector=embeddings[i],
                        ),
                    )
                    insert_count += 1
                return (len(res), None)
        except WeaviateBaseError as e:
            log.warning(f"Failed to insert data, error: {e!s}")
            return (insert_count, e)

    def search_embedding(
        self,
        query: list[float],
        k: int = 100,
        filters: dict | None = None,
        timeout: int | None = None,
    ) -> list[int]:
        """Perform a search on a query embedding and return results with distance.
        Should call self.init() first.
        """
        assert self.client.schema.exists(self.collection_name)

        query_obj = (
            self.client.query.get(self.collection_name, [self._scalar_field])
            .with_additional("distance")
            .with_near_vector({"vector": query})
            .with_limit(k)
        )
        # Use ConsistencyLevel.ONE for read scaling when replication is enabled.
        # This allows queries to return from a single replica (faster).
        # Requires Weaviate 1.26+ and replication_factor >= 3 at collection creation.
        if hasattr(self.case_config, 'replication_factor') and self.case_config.replication_factor is not None and self.case_config.replication_factor >= 3:
            try:
                from weaviate.data.replication import ConsistencyLevel
                query_obj = query_obj.with_consistency_level(ConsistencyLevel.ONE)
            except (ImportError, AttributeError):
                pass  # Weaviate client version doesn't support consistency level
        if filters:
            where_filter = {
                "path": "key",
                "operator": "GreaterThanEqual",
                "valueInt": filters.get("id"),
            }
            query_obj = query_obj.with_where(where_filter)

        res = query_obj.do()

        # Check for errors in response (GraphQL returns errors key when query fails)
        if "errors" in res:
            error_msg = str(res["errors"])
            raise RuntimeError(f"Weaviate query failed: {error_msg}")

        return [result[self._scalar_field] for result in res["data"]["Get"][self.collection_name]]
