# examples/tool_usage_example.py
"""
Example usage of the AI Analyst Tools

This file demonstrates how to use the various tools in the AI Analyst system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from tools import (
    ToolFactory, 
    QueryType,
    CompanySearchParams,
    PeopleSearchParams,
    EmailSearchParams,
    InteractionSearchParams,
    GroupSearchParams
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_workspace_operations():
    """Example of workspace operations"""
    logger.info("=== Workspace Operations Example ===")
    
    # Create workspace tool
    workspace_tool = ToolFactory.create_tool("workspace", "workspace-123", "user-456")
    
    # Get workspace info
    result = await workspace_tool.execute(QueryType.GET_BY_ID)
    logger.info(f"Workspace info: {result.data}")
    
    # Get workspace settings
    result = await workspace_tool.execute(QueryType.LIST)
    logger.info(f"Workspace settings: {result.data}")


async def example_company_operations():
    """Example of company operations"""
    logger.info("=== Company Operations Example ===")
    
    # Create company tool
    company_tool = ToolFactory.create_tool("company", "workspace-123", "user-456")
    
    # Search companies
    search_params = CompanySearchParams(
        name="Tech",
        privacy_level="PUBLIC",
        limit=10
    )
    result = await company_tool.execute(QueryType.SEARCH, **search_params.dict())
    logger.info(f"Company search results: {result.data}")
    
    # Get company analytics
    result = await company_tool.execute(QueryType.ANALYTICS)
    logger.info(f"Company analytics: {result.data}")


async def example_people_operations():
    """Example of people operations"""
    logger.info("=== People Operations Example ===")
    
    # Create people tool
    people_tool = ToolFactory.create_tool("people", "workspace-123", "user-456")
    
    # Search people
    search_params = PeopleSearchParams(
        job_title="Engineer",
        limit=5
    )
    result = await people_tool.execute(QueryType.SEARCH, **search_params.dict())
    logger.info(f"People search results: {result.data}")
    
    # Get people analytics
    result = await people_tool.execute(QueryType.ANALYTICS)
    logger.info(f"People analytics: {result.data}")


async def example_email_operations():
    """Example of email operations"""
    logger.info("=== Email Operations Example ===")
    
    # Create email tool
    email_tool = ToolFactory.create_tool("email", "workspace-123", "user-456")
    
    # Search emails
    search_params = EmailSearchParams(
        person_id="person-789",
        direction="sent",
        limit=20
    )
    result = await email_tool.execute(QueryType.SEARCH, **search_params.dict())
    logger.info(f"Email search results: {result.data}")
    
    # Get email analytics
    result = await email_tool.execute(QueryType.ANALYTICS)
    logger.info(f"Email analytics: {result.data}")


async def example_interaction_operations():
    """Example of interaction operations"""
    logger.info("=== Interaction Operations Example ===")
    
    # Create interaction tool
    interaction_tool = ToolFactory.create_tool("interaction", "workspace-123", "user-456")
    
    # Search interactions
    search_params = InteractionSearchParams(
        person_id="person-789",
        interaction_type="CALL",
        limit=10
    )
    result = await interaction_tool.execute(QueryType.SEARCH, **search_params.dict())
    logger.info(f"Interaction search results: {result.data}")
    
    # Get interaction analytics
    result = await interaction_tool.execute(QueryType.ANALYTICS)
    logger.info(f"Interaction analytics: {result.data}")


async def example_group_operations():
    """Example of group operations"""
    logger.info("=== Group Operations Example ===")
    
    # Create group tool
    group_tool = ToolFactory.create_tool("group", "workspace-123", "user-456")
    
    # Search groups
    search_params = GroupSearchParams(
        group_type="PEOPLE",
        is_private=False,
        limit=5
    )
    result = await group_tool.execute(QueryType.SEARCH, **search_params.dict())
    logger.info(f"Group search results: {result.data}")
    
    # Get group analytics
    result = await group_tool.execute(QueryType.ANALYTICS)
    logger.info(f"Group analytics: {result.data}")


async def example_tool_factory():
    """Example of tool factory operations"""
    logger.info("=== Tool Factory Example ===")
    
    # Get available tools
    available_tools = ToolFactory.get_available_tools()
    logger.info(f"Available tools: {available_tools}")
    
    # Get tool information
    for tool_name in available_tools:
        tool_info = ToolFactory.get_tool_info(tool_name)
        logger.info(f"Tool {tool_name}: {tool_info}")
    
    # Get all tools info
    all_tools_info = ToolFactory.get_all_tools_info()
    logger.info(f"All tools info: {all_tools_info}")


async def example_caching():
    """Example of caching functionality"""
    logger.info("=== Caching Example ===")
    
    # Create a tool
    company_tool = ToolFactory.create_tool("company", "workspace-123", "user-456")
    
    # First execution (cache miss)
    start_time = datetime.now()
    result1 = await company_tool.execute(QueryType.ANALYTICS)
    time1 = (datetime.now() - start_time).total_seconds() * 1000
    
    # Second execution (cache hit)
    start_time = datetime.now()
    result2 = await company_tool.execute(QueryType.ANALYTICS)
    time2 = (datetime.now() - start_time).total_seconds() * 1000
    
    logger.info(f"First execution time: {time1:.2f}ms, cached: {result1.cached}")
    logger.info(f"Second execution time: {time2:.2f}ms, cached: {result2.cached}")
    
    # Clear cache
    await company_tool.clear_cache()


async def main():
    """Main example function"""
    logger.info("Starting AI Analyst Tools Examples")
    
    try:
        # Run all examples
        await example_workspace_operations()
        await example_company_operations()
        await example_people_operations()
        await example_email_operations()
        await example_interaction_operations()
        await example_group_operations()
        await example_tool_factory()
        await example_caching()
        
        logger.info("All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
