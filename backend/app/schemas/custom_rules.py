"""Schemas for Custom Extraction and Custom Search API operations."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(StrEnum):
    xpath = "xpath"
    css = "css"
    regex = "regex"


class ExtractType(StrEnum):
    text = "text"
    html = "html"
    inner_html = "inner_html"
    attribute = "attribute"


class CustomExtractorBase(BaseModel):
    name: str = Field(..., max_length=100)
    method: ExtractionMethod
    selector: str
    extract_type: ExtractType = ExtractType.text
    attribute_name: str | None = None


class CustomExtractorCreate(CustomExtractorBase):
    pass


class CustomExtractorResponse(CustomExtractorBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crawl_id: uuid.UUID
    created_at: datetime


class CustomSearchBase(BaseModel):
    name: str = Field(..., max_length=100)
    pattern: str
    is_regex: bool = False
    case_sensitive: bool = False
    contains: bool = True  # True means trigger if found, False means trigger if not found


class CustomSearchCreate(CustomSearchBase):
    pass


class CustomSearchResponse(CustomSearchBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crawl_id: uuid.UUID
    created_at: datetime
