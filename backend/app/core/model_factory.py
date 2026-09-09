"""Single source of embedding (and, later, chat) model instances.

No node/service should construct a provider client directly — call
get_embeddings() so provider choice and the fake-embeddings test/budget
switch stay in one place.
"""

import hashlib
import struct

from app.core.config import settings


class FakeEmbeddings:
    """Deterministic, offline embedder: same text always yields the same vector.

    Used whenever settings.use_fake_embeddings is True (forced on in tests).
    Not semantically meaningful — only stable, so retrieval logic and chunk
    metadata can be tested without calling Azure and without cosine
    similarity being pure noise (identical/near-identical text still scores
    high on plain n-gram hashing).
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def _vector_for(self, text: str) -> list[float]:
        tokens = text.lower().split()
        vec = [0.0] * self.dimension
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, min(len(digest), 4)):
                idx = struct.unpack("B", digest[i : i + 1])[0] % self.dimension
                vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)


def get_embeddings():
    """Return the configured embedding client (fake or Azure OpenAI)."""
    if settings.use_fake_embeddings:
        return FakeEmbeddings(dimension=settings.embedding_dimension)

    if settings.llm_provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings

        return AzureOpenAIEmbeddings(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_embedding_deployment,
        )

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
