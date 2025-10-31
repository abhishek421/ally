# tools/__init__.py
"""
AI Analyst Tools Package

This package contains all the tools for the AI Analyst system.
Each tool inherits from BaseTool and implements specific data extraction logic.
"""

from .base_tool import BaseTool, ToolResult, QueryType
from .workspace_tool import WorkspaceTool
from .company_tool import CompanyTool, CompanySearchParams
from .people_tool import PeopleTool, PeopleSearchParams
from .emails_tool import EmailTool, EmailSearchParams
from .interaction_tool import InteractionTool, InteractionSearchParams
from .group_tool import GroupTool, GroupSearchParams
from .tool_factory import ToolFactory

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult", 
    "QueryType",
    
    # Tool implementations
    "WorkspaceTool",
    "CompanyTool",
    "PeopleTool", 
    "EmailTool",
    "InteractionTool",
    "GroupTool",
    
    # Search parameter models
    "CompanySearchParams",
    "PeopleSearchParams",
    "EmailSearchParams", 
    "InteractionSearchParams",
    "GroupSearchParams",
    
    # Factory
    "ToolFactory"
]