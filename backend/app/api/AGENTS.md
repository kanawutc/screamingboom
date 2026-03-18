# API Layer — AGENTS.md

## Pattern: Router → Service → Repository

Every endpoint follows this flow:
1. Router handler receives request with DI-injected dependencies
2. Instantiates service: `svc = CrawlService(db, redis)`
3. Calls service method
4. Returns Pydantic response model

## Dependency Injection (deps.py)

```python
# Type aliases for clean signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
RawPool = Annotated[asyncpg.Pool, Depends(get_raw_pool)]
```

Use these aliases in endpoint signatures — never call `Depends()` inline.

## Endpoint Pattern (follow this exactly)

```python
router = APIRouter(prefix="/resources", tags=["resources"])

@router.post("", status_code=201, response_model=ResourceResponse)
async def create_resource(
    data: ResourceCreate,
    db: DbSession,
) -> ResourceResponse:
    svc = ResourceService(db)
    resource = await svc.create(data)
    return ResourceResponse.model_validate(resource)

@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: uuid.UUID,
    db: DbSession,
) -> ResourceResponse:
    svc = ResourceService(db)
    resource = await svc.get_by_id(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return ResourceResponse.model_validate(resource)
```

## Router Files

| File | Prefix | Endpoints |
|------|--------|-----------|
| `v1/projects.py` | `/projects` | CRUD (5 endpoints) |
| `v1/crawls.py` | `/crawls` | Start, list, get, pause/resume/stop, delete, WebSocket (10+ endpoints) |
| `v1/urls.py` | `/crawls/{id}/urls` | List URLs, detail, inlinks, outlinks, external links, export CSV/XLSX, sitemap XML, structured data, custom extractions, pagination (10+ endpoints) |
| `v1/issues.py` | `/crawls/{id}/issues` | List issues, summary (2 endpoints) |
| `v1/comparison.py` | `/crawls/compare` | Compare two crawls (1 endpoint) |
| `v1/extraction_rules.py` | `/projects/{id}/extraction-rules` | CRUD extraction rules (4 endpoints) |

## Pagination Pattern

Cursor-based (keyset), NOT offset:
```python
@router.get("", response_model=dict)
async def list_resources(
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: DbSession,
) -> dict:
    # Returns: {"items": [...], "next_cursor": "...", "total": N}
```

## Error Handling

- 404: `raise HTTPException(status_code=404, detail="X not found")`
- 400: `raise HTTPException(status_code=400, detail="Invalid X")`
- 409: `raise HTTPException(status_code=409, detail="X already running")`
- Validation errors handled by FastAPI/Pydantic automatically (422).
- Unhandled exceptions caught by `core/exceptions.py` → JSON with structlog.

## WebSocket Endpoint

```python
@router.websocket("/crawls/{crawl_id}/ws")
async def crawl_websocket(websocket: WebSocket, crawl_id: uuid.UUID):
    await websocket.accept()
    queue = asyncio.Queue(maxsize=100)
    broadcaster.subscribe(crawl_id, queue)
    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(msg)
    finally:
        broadcaster.unsubscribe(crawl_id, queue)
```

Message types: `progress`, `status_change`, `ping` (30s heartbeat).

## Response Model Convention

- `ResourceResponse` — single item (from_attributes=True)
- `ResourceCreate` — POST body
- `ResourceUpdate` — PUT body (all fields optional)
- Paginated responses return raw dict: `{"items": [...], "next_cursor": "...", "total": N}`
