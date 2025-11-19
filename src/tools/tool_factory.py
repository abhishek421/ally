# tools/tool_factory.py
from typing import Dict, Type, List
from src.tools.base_tool import BaseTool
from src.tools.workspace.workspace_tool import WorkspaceTool
from src.tools.crm.company_tool import CompanyTool
from src.tools.crm.people_tool import PeopleTool
from src.tools.communication.emails_tool import EmailTool
from src.tools.communication.interaction_tool import InteractionTool
from src.tools.crm.group_tool import GroupTool
import logging

logger = logging.getLogger(__name__)


class ToolFactory:
    """Factory for creating tool instances"""
    
    _tool_registry: Dict[str, Type[BaseTool]] = {
        'workspace': WorkspaceTool,
        'company': CompanyTool,
        'people': PeopleTool,
        'email': EmailTool,
        'interaction': InteractionTool,
        'group': GroupTool,
    }
    
    @classmethod
    def create_tool(cls, tool_name: str, workspace_id: str, user_id: str) -> BaseTool:
        """Create a tool instance"""
        if tool_name not in cls._tool_registry:
            available_tools = list(cls._tool_registry.keys())
            raise ValueError(f"Unknown tool: {tool_name}. Available tools: {available_tools}")
        
        try:
            tool_class = cls._tool_registry[tool_name]
            tool_instance = tool_class(workspace_id, user_id)
            logger.info(f"Created {tool_name} tool for workspace {workspace_id}")
            return tool_instance
        except Exception as e:
            logger.error(f"Failed to create {tool_name} tool: {e}")
            raise
    
    @classmethod
    def get_available_tools(cls) -> List[str]:
        """Get list of available tools"""
        return list(cls._tool_registry.keys())
    
    @classmethod
    def register_tool(cls, name: str, tool_class: Type[BaseTool]):
        """Register a new tool"""
        if not issubclass(tool_class, BaseTool):
            raise ValueError(f"Tool class must inherit from BaseTool")
        
        cls._tool_registry[name] = tool_class
        logger.info(f"Registered new tool: {name}")
    
    @classmethod
    def unregister_tool(cls, name: str):
        """Unregister a tool"""
        if name in cls._tool_registry:
            del cls._tool_registry[name]
            logger.info(f"Unregistered tool: {name}")
        else:
            logger.warning(f"Tool {name} not found in registry")
    
    @classmethod
    def get_tool_info(cls, tool_name: str) -> Dict[str, any]:
        """Get information about a tool"""
        if tool_name not in cls._tool_registry:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_class = cls._tool_registry[tool_name]
        
        # Create a temporary instance to get supported operations
        try:
            temp_instance = tool_class("temp_workspace", "temp_user")
            supported_operations = temp_instance.get_supported_operations()
        except Exception as e:
            logger.error(f"Error getting tool info for {tool_name}: {e}")
            supported_operations = []
        
        return {
            "name": tool_name,
            "class": tool_class.__name__,
            "module": tool_class.__module__,
            "supported_operations": [op.value for op in supported_operations],
            "description": tool_class.__doc__ or "No description available"
        }
    
    @classmethod
    def get_all_tools_info(cls) -> Dict[str, Dict[str, any]]:
        """Get information about all registered tools"""
        return {
            tool_name: cls.get_tool_info(tool_name)
            for tool_name in cls._tool_registry.keys()
        }
