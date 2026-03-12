"""CRUD endpoints for custom extraction rules, nested under projects."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.models.extraction_rule import ExtractionRule
from app.schemas.extraction_rule import (
    ExtractionRuleCreate,
    ExtractionRuleResponse,
    ExtractionRuleUpdate,
)

router = APIRouter(
    prefix="/projects/{project_id}/extraction-rules",
    tags=["extraction-rules"],
)


@router.post("", response_model=ExtractionRuleResponse, status_code=201)
async def create_rule(
    project_id: uuid.UUID, data: ExtractionRuleCreate, db: DbSession
) -> ExtractionRuleResponse:
    rule = ExtractionRule(
        project_id=project_id,
        name=data.name,
        selector=data.selector,
        selector_type=data.selector_type,
        extract_type=data.extract_type,
        attribute_name=data.attribute_name,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return ExtractionRuleResponse.model_validate(rule)


@router.get("", response_model=list[ExtractionRuleResponse])
async def list_rules(project_id: uuid.UUID, db: DbSession) -> list[ExtractionRuleResponse]:
    result = await db.execute(
        sa.select(ExtractionRule)
        .where(ExtractionRule.project_id == project_id)
        .order_by(ExtractionRule.created_at)
    )
    rules = result.scalars().all()
    return [ExtractionRuleResponse.model_validate(r) for r in rules]


@router.get("/{rule_id}", response_model=ExtractionRuleResponse)
async def get_rule(
    project_id: uuid.UUID, rule_id: uuid.UUID, db: DbSession
) -> ExtractionRuleResponse:
    rule = await db.get(ExtractionRule, rule_id)
    if not rule or rule.project_id != project_id:
        raise HTTPException(status_code=404, detail="Extraction rule not found")
    return ExtractionRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=ExtractionRuleResponse)
async def update_rule(
    project_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ExtractionRuleUpdate,
    db: DbSession,
) -> ExtractionRuleResponse:
    rule = await db.get(ExtractionRule, rule_id)
    if not rule or rule.project_id != project_id:
        raise HTTPException(status_code=404, detail="Extraction rule not found")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(rule, k, v)
    await db.commit()
    await db.refresh(rule)
    return ExtractionRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(project_id: uuid.UUID, rule_id: uuid.UUID, db: DbSession) -> None:
    rule = await db.get(ExtractionRule, rule_id)
    if not rule or rule.project_id != project_id:
        raise HTTPException(status_code=404, detail="Extraction rule not found")
    await db.delete(rule)
    await db.commit()
