import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    selector: str = Field(..., min_length=1)
    selector_type: Literal["css", "xpath"] = "css"
    extract_type: Literal["text", "html", "attribute", "count"] = "text"
    attribute_name: str | None = None


class ExtractionRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    selector: str | None = Field(None, min_length=1)
    selector_type: Literal["css", "xpath"] | None = None
    extract_type: Literal["text", "html", "attribute", "count"] | None = None
    attribute_name: str | None = None


class ExtractionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    selector: str
    selector_type: str
    extract_type: str
    attribute_name: str | None
    created_at: datetime
    updated_at: datetime
