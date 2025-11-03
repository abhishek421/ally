"""
Pydantic models for LLM configuration
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class GlobalLLMConfigModel(BaseModel):
    """Global LLM configuration model"""
    id: str
    provider: str = Field(..., description="LLM provider: 'openai', 'anthropic', or 'gemini'")
    model: str = Field(..., description="Model name (e.g., 'gpt-4', 'claude-3-opus')")
    enabled: bool = Field(default=True, description="Whether this config is enabled")
    version: int = Field(default=1, description="Config version for tracking changes")
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True


class AgentLLMConfigModel(BaseModel):
    """Agent-specific LLM configuration model"""
    id: str
    agentName: str = Field(..., description="Agent name: 'query_optimizer', 'data_extractor', 'response_formatter'")
    provider: Optional[str] = Field(None, description="Override provider. None = use global")
    model: Optional[str] = Field(None, description="Override model. None = use global")
    enabled: bool = Field(default=True, description="Whether this config is enabled")
    version: int = Field(default=1, description="Config version for tracking changes")
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True


class LLMConfig(BaseModel):
    """
    Combined LLM configuration with resolved values
    This represents the final configuration for an agent after inheritance logic
    """
    provider: str = Field(..., description="Resolved provider name")
    model: str = Field(..., description="Resolved model name")
    api_key: str = Field(default="", description="API key from environment variables")
    source: str = Field(..., description="Source of config: 'db_agent', 'db_global', 'env', or 'default'")
    agent_name: Optional[str] = Field(None, description="Agent name this config is for")
    
    def to_dict(self) -> dict:
        """Convert to dictionary format for LLMProviderFactory"""
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key
        }

