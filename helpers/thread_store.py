"""Durable storage for Agent Framework thread state backed by Azure Cosmos DB."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from azure.cosmos import PartitionKey, exceptions
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


class AgentThreadStore:
    """Persists serialized AgentThread state inside Azure Cosmos DB for durability."""

    def __init__(
        self,
        *,
        endpoint: str,
        key: Optional[str],
        database_name: str,
        container_name: str,
        partition_key_path: str = "/threadId",
        throughput: Optional[int] = None,
        use_default_credential: bool = False,
    ) -> None:
        if not endpoint:
            raise ValueError("COSMOSDB_ENDPOINT must be configured.")

        if not key and not use_default_credential:
            raise ValueError(
                "Provide COSMOSDB_KEY or enable DefaultAzureCredential usage."
            )

        self._credential: Optional[DefaultAzureCredential] = None
        credential: Any = key
        if not key or use_default_credential:
            self._credential = DefaultAzureCredential()
            credential = self._credential

        self._client = CosmosClient(endpoint, credential=credential)
        self._database_name = database_name
        self._container_name = container_name
        self._partition_key_path = partition_key_path
        self._throughput = throughput

        self._container = None
        self._init_lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> "AgentThreadStore":
        endpoint = os.getenv("COSMOS_ENDPOINT", "").strip()
        key = os.getenv("COSMOS_KEY")
        if key is not None:
            key = key.strip()
        use_default_credential = os.getenv(
            "COSMOS_USE_DEFAULT_CREDENTIAL", "false"
        ).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not key:
            use_default_credential = True
        database = os.getenv("COSMOS_DATABASE_NAME", "bot-data").strip() or "bot-data"
        container = (
            os.getenv("COSMOS_CONTAINER_NAME", "agent-threads").strip()
            or "agent-threads"
        )
        partition_key = os.getenv("COSMOS_PARTITION_KEY_PATH", "/threadId")
        throughput_raw = os.getenv("COSMOS_CONTAINER_THROUGHPUT")
        throughput = int(throughput_raw) if throughput_raw else None

        return cls(
            endpoint=endpoint,
            key=key,
            database_name=database,
            container_name=container,
            partition_key_path=partition_key,
            throughput=throughput,
            use_default_credential=use_default_credential,
        )

    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        container = await self._ensure_container()
        try:
            item = await container.read_item(item=key, partition_key=key)
            payload = item.get("threadState")
            message_count = (
                len(payload.get("chat_message_store_state", {}).get("messages", []))
                if payload
                else 0
            )
            logger.info(
                "Loaded thread for %s from Cosmos DB with %s messages.",
                key,
                message_count,
            )
            return payload
        except exceptions.CosmosResourceNotFoundError:
            logger.info("No thread found in Cosmos DB for key: %s", key)
            return None
        except Exception as exc:
            logger.exception(
                "Failed to load thread for %s from Cosmos DB", key, exc_info=exc
            )
            return None

    async def save(self, key: str, state: Dict[str, Any]) -> None:
        container = await self._ensure_container()
        document = {
            "id": key,
            "threadId": key,
            "threadState": state,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        await container.upsert_item(body=document)
        message_count = len(
            state.get("chat_message_store_state", {}).get("messages", [])
        )
        logger.info(
            "Upserted thread state for %s with %s messages.", key, message_count
        )

    async def delete(self, key: str) -> None:
        container = await self._ensure_container()
        try:
            await container.delete_item(item=key, partition_key=key)
            logger.debug("Deleted thread state for %s from Cosmos DB.", key)
        except exceptions.CosmosResourceNotFoundError:
            logger.debug("Thread state for %s was already absent.", key)

    async def close(self) -> None:
        await self._client.close()
        if self._credential:
            await self._credential.close()

    async def _ensure_container(self):  # type: ignore[no-untyped-def]
        if self._container is not None:
            return self._container

        async with self._init_lock:
            if self._container is None:
                database = await self._client.create_database_if_not_exists(
                    id=self._database_name
                )
                partition_key = PartitionKey(path=self._partition_key_path)
                container_kwargs: Dict[str, Any] = {
                    "id": self._container_name,
                    "partition_key": partition_key,
                }
                if self._throughput:
                    container_kwargs["offer_throughput"] = self._throughput

                container = await database.create_container_if_not_exists(
                    **container_kwargs
                )
                self._container = container
        return self._container
