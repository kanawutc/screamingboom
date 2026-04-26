"""Repository for managing custom extractors and searches via asyncpg pool."""

import uuid

import asyncpg

from app.schemas.custom_rules import CustomExtractorCreate, CustomSearchCreate


class CustomRulesRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def list_extractors(self, crawl_id: uuid.UUID) -> list[dict]:
        """List all custom extractors for a crawl."""
        query = "SELECT * FROM custom_extractors WHERE crawl_id = $1 ORDER BY created_at ASC"
        rows = await self._pool.fetch(query, crawl_id)
        return [dict(r) for r in rows]

    async def create_extractor(
        self, crawl_id: uuid.UUID, extractor: CustomExtractorCreate
    ) -> dict:
        """Create a new custom extractor."""
        query = """
            INSERT INTO custom_extractors (crawl_id, name, method, selector, extract_type, attribute_name)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            query,
            crawl_id,
            extractor.name,
            extractor.method.value,
            extractor.selector,
            extractor.extract_type.value,
            extractor.attribute_name,
        )
        return dict(row)

    async def delete_extractor(self, extractor_id: uuid.UUID) -> bool:
        """Delete a custom extractor."""
        query = "DELETE FROM custom_extractors WHERE id = $1"
        status = await self._pool.execute(query, extractor_id)
        return status == "DELETE 1"

    async def list_searches(self, crawl_id: uuid.UUID) -> list[dict]:
        """List all custom searches for a crawl."""
        query = "SELECT * FROM custom_searches WHERE crawl_id = $1 ORDER BY created_at ASC"
        rows = await self._pool.fetch(query, crawl_id)
        return [dict(r) for r in rows]

    async def create_search(self, crawl_id: uuid.UUID, search: CustomSearchCreate) -> dict:
        """Create a new custom search."""
        query = """
            INSERT INTO custom_searches (crawl_id, name, pattern, is_regex, case_sensitive, contains)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            query,
            crawl_id,
            search.name,
            search.pattern,
            search.is_regex,
            search.case_sensitive,
            search.contains,
        )
        return dict(row)

    async def delete_search(self, search_id: uuid.UUID) -> bool:
        """Delete a custom search."""
        query = "DELETE FROM custom_searches WHERE id = $1"
        status = await self._pool.execute(query, search_id)
        return status == "DELETE 1"

    async def get_extraction_results(self, crawl_id: uuid.UUID, limit: int = 100) -> list[dict]:
        """Fetch extraction results with extractor name and URL."""
        query = """
            SELECT ce.id, ce.extracted_value, ce.created_at, e.name as extractor_name, u.url
            FROM custom_extractions ce
            JOIN custom_extractors e ON ce.extractor_id = e.id
            JOIN crawled_urls u ON ce.url_id = u.id AND ce.crawl_id = u.crawl_id
            WHERE ce.crawl_id = $1
            ORDER BY ce.created_at DESC
            LIMIT $2
        """
        rows = await self._pool.fetch(query, crawl_id, limit)
        return [dict(r) for r in rows]

    async def get_search_results(self, crawl_id: uuid.UUID, limit: int = 100) -> list[dict]:
        """Fetch custom search results."""
        query = """
            SELECT csr.id, csr.found_count, csr.created_at, s.name as search_name, s.pattern, u.url
            FROM custom_search_results csr
            JOIN custom_searches s ON csr.search_id = s.id
            JOIN crawled_urls u ON csr.url_id = u.id AND csr.crawl_id = u.crawl_id
            WHERE csr.crawl_id = $1
            ORDER BY csr.created_at DESC
            LIMIT $2
        """
        rows = await self._pool.fetch(query, crawl_id, limit)
        return [dict(r) for r in rows]
