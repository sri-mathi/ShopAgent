from abc import ABC, abstractmethod

from shopagent_core.models import Order, Product


class StoreAdapter(ABC):
    """The contract any store's data source must satisfy to work with the
    agent. Deliberately narrow: each method answers the simplest possible
    question about the store's data. Anything correctness- or security-
    sensitive built on top of that data (order-ownership verification,
    policy retrieval/RAG) is handled centrally in services/, not here - so
    every adapter gets the same guarantees for free, regardless of who
    wrote it or what backend it talks to."""

    @abstractmethod
    def get_products(
        self,
        keyword: str | None = None,
        category: str | None = None,
        color: str | None = None,
        max_price: float | None = None,
    ) -> list[Product]:
        """Return in-stock products matching the given filters."""

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Return the order if it exists, by ID alone. Do NOT check the
        customer's email here - ownership verification (including the
        anti-enumeration guarantee that a wrong email and a nonexistent
        order look identical) is centralized in services/order_lookup.py."""

    @abstractmethod
    def get_policy_documents(self) -> str:
        """Return this store's raw policy text (markdown or plain text).
        Chunking, embedding, and similarity search are handled centrally in
        services/policy_rag.py - this method's only job is fetching the
        raw source text, however this store happens to store it."""
