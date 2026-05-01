from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AgentConfigBase(BaseModel):
    """Base schema for agent configuration"""
    system_prompt: str | None = None
    personality_prompt: str | None = None


class AgentConfigCreate(AgentConfigBase):
    """Schema for creating agent configuration"""
    pass


class AgentConfigUpdate(BaseModel):
    """Schema for updating agent configuration"""
    system_prompt: str | None = None
    personality_prompt: str | None = None


class AgentConfigResponse(BaseModel):
    """Schema for agent configuration response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    system_prompt: str | None
    personality_prompt: str | None
    is_configured: bool
    created_at: datetime
    updated_at: datetime


class AgentTestRequest(BaseModel):
    """Schema for testing agent"""
    question: str
    context: str | None = None


class AgentTestResponse(BaseModel):
    """Schema for agent test response"""
    answer: str
    sources: list[str] = []
    agent_config_used: bool = False
    wiki_context: bool = False
    web_search_used: bool = False