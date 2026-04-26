"""API routes for configuring and fetching custom extractors and searches."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AsyncpgPool
from app.repositories.custom_rules_repo import CustomRulesRepository
from app.schemas.custom_rules import (
    CustomExtractorCreate,
    CustomExtractorResponse,
    CustomSearchCreate,
    CustomSearchResponse,
)

router = APIRouter(tags=["custom-rules"])


@router.get("/crawls/{crawl_id}/extractors", response_model=list[CustomExtractorResponse])
async def list_extractors(crawl_id: uuid.UUID, pool: AsyncpgPool) -> list[dict]:
    """List all custom extractors for a crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.list_extractors(crawl_id)


@router.post(
    "/crawls/{crawl_id}/extractors",
    response_model=CustomExtractorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_extractor(
    crawl_id: uuid.UUID, extractor: CustomExtractorCreate, pool: AsyncpgPool
) -> dict:
    """Create a new custom extractor for a crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.create_extractor(crawl_id, extractor)


@router.delete("/extractors/{extractor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_extractor(extractor_id: uuid.UUID, pool: AsyncpgPool) -> None:
    """Delete a custom extractor."""
    repo = CustomRulesRepository(pool)
    await repo.delete_extractor(extractor_id)


@router.get("/crawls/{crawl_id}/searches", response_model=list[CustomSearchResponse])
async def list_searches(crawl_id: uuid.UUID, pool: AsyncpgPool) -> list[dict]:
    """List all custom searches for a crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.list_searches(crawl_id)


@router.post(
    "/crawls/{crawl_id}/searches",
    response_model=CustomSearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_search(
    crawl_id: uuid.UUID, search: CustomSearchCreate, pool: AsyncpgPool
) -> dict:
    """Create a new custom search for a crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.create_search(crawl_id, search)


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search(search_id: uuid.UUID, pool: AsyncpgPool) -> None:
    """Delete a custom search."""
    repo = CustomRulesRepository(pool)
    await repo.delete_search(search_id)


@router.get("/crawls/{crawl_id}/extractions")
async def get_extractions(crawl_id: uuid.UUID, pool: AsyncpgPool, limit: int = 100) -> list[dict]:
    """Get the extraction results for a completed crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.get_extraction_results(crawl_id, limit=limit)


@router.get("/crawls/{crawl_id}/search-results")
async def get_search_results(crawl_id: uuid.UUID, pool: AsyncpgPool, limit: int = 100) -> list[dict]:
    """Get the custom search results for a completed crawl."""
    repo = CustomRulesRepository(pool)
    return await repo.get_search_results(crawl_id, limit=limit)
