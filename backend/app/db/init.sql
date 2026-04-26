-- PostgreSQL extensions for SEO Spider
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Custom Extraction (Sprint 4)
CREATE TABLE IF NOT EXISTS custom_extractors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    method VARCHAR(20) NOT NULL,
    selector TEXT NOT NULL,
    extract_type VARCHAR(20) NOT NULL DEFAULT 'text',
    attribute_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url_id UUID NOT NULL,
    extractor_id UUID NOT NULL REFERENCES custom_extractors(id) ON DELETE CASCADE,
    extracted_value TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (url_id, crawl_id) REFERENCES crawled_urls(id, crawl_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_custom_extractions_url ON custom_extractions(url_id);
CREATE INDEX IF NOT EXISTS idx_custom_extractions_crawl ON custom_extractions(crawl_id);

-- Custom Search (Sprint 4)
CREATE TABLE IF NOT EXISTS custom_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    pattern TEXT NOT NULL,
    is_regex BOOLEAN DEFAULT FALSE,
    case_sensitive BOOLEAN DEFAULT FALSE,
    contains BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url_id UUID NOT NULL,
    search_id UUID NOT NULL REFERENCES custom_searches(id) ON DELETE CASCADE,
    found_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (url_id, crawl_id) REFERENCES crawled_urls(id, crawl_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_custom_search_results_url ON custom_search_results(url_id);
CREATE INDEX IF NOT EXISTS idx_custom_search_results_crawl ON custom_search_results(crawl_id);
