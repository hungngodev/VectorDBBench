"""Wrapper around the Weaviate vector database over VectorDB"""

import logging
import os
import subprocess
import socket
from collections.abc import Iterable
from contextlib import contextmanager
from urllib.parse import urlparse

import weaviate
from weaviate.data.replication import ConsistencyLevel
from weaviate.exceptions import WeaviateBaseError

from ..api import DBCaseConfig, VectorDB

log = logging.getLogger(__name__)


def resolve_all_pod_ips(hostname: str) -> list[str]:
    """
    Resolve all IPs for a hostname using getent (bypasses Python DNS caching).
    This is essential for client-side load balancing with K8s headless services.
    
    Args:
        hostname: The hostname to resolve (e.g., weaviate-headless.namespace.svc.cluster.local)
    
    Returns:
        List of IP addresses, or empty list if resolution fails
    """
    try:
        # Use getent to bypass Python's DNS cache and get ALL IPs
        result = subprocess.run(
            ["getent", "ahostsv4", hostname],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            ips = set()
            for line in result.stdout.strip().split('\n'):
                if line:
                    ip = line.split()[0]
                    ips.add(ip)
            return list(ips)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback to socket (may return cached/single IP)
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        return list(set(addr[4][0] for addr in addrs))
    except Exception:
        return []


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

        # If local setup is used, we
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
        Initialize client with client-side load balancing for K8s headless services.
        
        When using a K8s headless service, this method:
        1. Resolves all pod IPs from the service
        2. Picks a specific pod based on process ID (round-robin)
        3. Connects directly to that pod for query execution
        
        This achieves proper query distribution across Weaviate pods,
        bypassing K8s Service connection-level (Layer 4) balancing limitations.
        
        Examples:
            >>> with self.init():
            >>>     self.insert_embeddings()
            >>>     self.search_embedding()
        """
        from weaviate import Client
        
        # Parse the original URL to extract host and port
        original_url = self.db_config.get("url", "")
        parsed = urlparse(original_url)
        hostname = parsed.hostname or ""
        port = parsed.port or 8080
        scheme = parsed.scheme or "http"
        
        # Check if this looks like a K8s headless service (contains 'headless' or 'svc.cluster')
        use_client_lb = "headless" in hostname or "svc.cluster" in hostname
        
        if use_client_lb:
            # Resolve all pod IPs for client-side load balancing
            all_ips = resolve_all_pod_ips(hostname)
            
            if all_ips and len(all_ips) > 1:
                # Pick a pod based on process ID for round-robin distribution
                worker_id = os.getpid()
                selected_ip = all_ips[worker_id % len(all_ips)]
                
                # Create a modified config pointing to the specific pod IP
                modified_config = self.db_config.copy()
                modified_config["url"] = f"{scheme}://{selected_ip}:{port}"
                
                log.debug(f"Client-side LB: worker {worker_id} connecting to pod {selected_ip} "
                         f"(1 of {len(all_ips)} pods)")
                
                self.client = Client(**modified_config)
            else:
                # Fallback to original URL if resolution fails or only 1 IP
                log.debug(f"Client-side LB: using original URL (resolved {len(all_ips)} IPs)")
                self.client = Client(**self.db_config)
        else:
            # Not a headless service, use standard connection
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
            
            # Add replication config for distributed query support
            replication_config = self.case_config.replication_param()
            if replication_config:
                class_obj["replicationConfig"] = replication_config
                log.info(f"Creating collection with replicationConfig: {replication_config}")
            
            try:
                client.schema.create_class(class_obj)
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
            .with_consistency_level(ConsistencyLevel.ONE)
        )
        if filters:
            where_filter = {
                "path": "key",
                "operator": "GreaterThanEqual",
                "valueInt": filters.get("id"),
            }
            query_obj = query_obj.with_where(where_filter)

        # Perform the search.
        res = query_obj.do()

        # Organize results.
        return [result[self._scalar_field] for result in res["data"]["Get"][self.collection_name]]
