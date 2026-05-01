"""Agent Configuration API Routes"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import Tenant, AgentConfig
from app.schemas.agent import (
    AgentConfigCreate, AgentConfigUpdate, AgentConfigResponse,
    AgentTestRequest, AgentTestResponse,
)
from app.services.agent_service import AgentService
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/agent", tags=["Agent Configuration"])


@router.get("/config", response_model=AgentConfigResponse)
async def get_agent_config(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get agent configuration for current tenant"""
    agent_service = AgentService(db)
    config = await agent_service.get_or_create_config(current_tenant.id)
    return config


@router.post("/config", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_config(
    config_data: AgentConfigCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create or update agent configuration"""
    agent_service = AgentService(db)
    update_data = AgentConfigUpdate(
        system_prompt=config_data.system_prompt,
        personality_prompt=config_data.personality_prompt,
    )
    config = await agent_service.update_config(current_tenant.id, update_data)
    return config


@router.patch("/config", response_model=AgentConfigResponse)
async def update_agent_config(
    config_data: AgentConfigUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update agent configuration"""
    agent_service = AgentService(db)
    config = await agent_service.update_config(current_tenant.id, config_data)
    return config


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_config(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete agent configuration"""
    agent_service = AgentService(db)
    success = await agent_service.delete_config(current_tenant.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent configuration not found",
        )


@router.post("/test", response_model=AgentTestResponse)
async def test_agent(
    test_request: AgentTestRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Test agent with a sample question"""
    agent_service = AgentService(db)
    result = await agent_service.test_agent(current_tenant.id, test_request)
    return result


@router.get("/status")
async def get_agent_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get agent configuration status"""
    agent_service = AgentService(db)
    status_data = await agent_service.get_agent_status(current_tenant.id)
    return status_data