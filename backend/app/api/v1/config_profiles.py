"""Config Profile API routes — CRUD for crawl configuration presets."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update, delete

from app.api.deps import DbSession
from app.models.config_profile import ConfigProfile
from app.schemas.config_profile import ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/config-profiles", tags=["config-profiles"])


@router.get("", response_model=list[ProfileResponse])
async def list_profiles(db: DbSession) -> list[ProfileResponse]:
    """List all configuration profiles."""
    result = await db.execute(
        select(ConfigProfile).order_by(ConfigProfile.is_default.desc(), ConfigProfile.name)
    )
    profiles = result.scalars().all()
    return [ProfileResponse.model_validate(p) for p in profiles]


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(data: ProfileCreate, db: DbSession) -> ProfileResponse:
    """Create a new configuration profile."""
    # If setting as default, unset existing defaults
    if data.is_default:
        await db.execute(
            update(ConfigProfile).where(ConfigProfile.is_default.is_(True)).values(is_default=False)
        )

    profile = ConfigProfile(
        name=data.name,
        description=data.description,
        config=data.config.model_dump(),
        is_default=data.is_default,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: uuid.UUID, db: DbSession) -> ProfileResponse:
    """Get a profile by ID."""
    result = await db.execute(select(ConfigProfile).where(ConfigProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse.model_validate(profile)


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: uuid.UUID,
    data: ProfileUpdate,
    db: DbSession,
) -> ProfileResponse:
    """Update a configuration profile."""
    result = await db.execute(select(ConfigProfile).where(ConfigProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    if data.is_default:
        await db.execute(
            update(ConfigProfile).where(ConfigProfile.is_default.is_(True)).values(is_default=False)
        )

    update_data: dict = {"updated_at": datetime.now(timezone.utc)}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.config is not None:
        update_data["config"] = data.config.model_dump()
    if data.is_default is not None:
        update_data["is_default"] = data.is_default

    await db.execute(
        update(ConfigProfile).where(ConfigProfile.id == profile_id).values(**update_data)
    )
    await db.commit()

    result = await db.execute(select(ConfigProfile).where(ConfigProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    return ProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: uuid.UUID, db: DbSession) -> None:
    """Delete a configuration profile."""
    result = await db.execute(
        delete(ConfigProfile).where(ConfigProfile.id == profile_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.commit()
