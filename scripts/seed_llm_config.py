"""
Database seeding script for LLM configuration
Creates default global and agent configurations if they don't exist.
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.prisma_client import prisma_client
from config.config_manager import get_config_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def seed_global_config():
    """
    Seed global LLM configuration from environment variables.

    Requires GLOBAL_LLM_PROVIDER and GLOBAL_LLM_MODEL to be set.
    """
    try:
        client = await prisma_client.get_client()

        # Check if global config exists
        existing = await client.globalllmconfig.find_first(where={"enabled": True})

        if existing:
            logger.info(f"Global LLM config already exists: {existing.provider}/{existing.model}")
            return existing
        else:
            # Get configuration from environment variables
            provider = os.getenv("GLOBAL_LLM_PROVIDER")
            model = os.getenv("GLOBAL_LLM_MODEL")

            if not provider or not model:
                raise ValueError(
                    "GLOBAL_LLM_PROVIDER and GLOBAL_LLM_MODEL environment variables "
                    "must be set to seed global configuration. "
                    f"Current values: provider='{provider}', model='{model}'"
                )

            # Create global config from env vars
            config = await client.globalllmconfig.create(
                data={
                    "provider": provider,
                    "model": model,
                    "enabled": True,
                    "version": 1
                }
            )
            logger.info(f"Created global LLM config from environment: {config.provider}/{config.model}")
            return config

    except Exception as e:
        logger.error(f"Error seeding global config: {e}")
        raise


async def seed_agent_config(agent_name: str, provider: str = None, model: str = None):
    """
    Seed agent-specific LLM configuration
    
    Args:
        agent_name: Name of the agent
        provider: Override provider (None = inherit from global)
        model: Override model (None = inherit from global)
    """
    try:
        client = await prisma_client.get_client()
        
        # Check if agent config exists
        existing = await client.agentllmconfig.find_unique(
            where={"agentName": agent_name}
        )
        
        if existing:
            logger.info(f"Agent config for '{agent_name}' already exists")
            return existing
        else:
            # Create agent config
            data = {
                "agentName": agent_name,
                "enabled": True,
                "version": 1
            }
            
            # Only set provider/model if provided (otherwise inherit from global)
            if provider:
                data["provider"] = provider
            if model:
                data["model"] = model
            
            config = await client.agentllmconfig.create(data=data)
            logger.info(f"Created agent config for '{agent_name}': {config.provider or 'inherit'}/{config.model or 'inherit'}")
            return config
            
    except Exception as e:
        logger.error(f"Error seeding agent config for '{agent_name}': {e}")
        raise


async def seed_all_configs():
    """
    Seed all LLM configurations from environment variables.

    Environment variables used:
    - GLOBAL_LLM_PROVIDER and GLOBAL_LLM_MODEL (required for global config)
    - <AGENT>_PROVIDER and <AGENT>_MODEL (optional for agent-specific overrides)

    Agents will inherit from global config unless specific overrides are set.
    """
    logger.info("Starting LLM configuration seeding...")

    try:
        # Connect to database
        await prisma_client.connect()
        logger.info("Connected to database")

        # Seed global config (requires env vars)
        await seed_global_config()

        # Seed agent configs (using None for provider/model = inherit from global)
        # Check environment variables for agent-specific overrides
        agents = [
            {
                "name": "query_optimizer",
                "provider": os.getenv("QUERY_OPTIMIZER_PROVIDER"),
                "model": os.getenv("QUERY_OPTIMIZER_MODEL")
            },
            {
                "name": "data_extractor",
                "provider": os.getenv("DATA_EXTRACTOR_PROVIDER"),
                "model": os.getenv("DATA_EXTRACTOR_MODEL")
            },
            {
                "name": "response_formatter",
                "provider": os.getenv("RESPONSE_FORMATTER_PROVIDER"),
                "model": os.getenv("RESPONSE_FORMATTER_MODEL")
            }
        ]

        for agent in agents:
            await seed_agent_config(
                agent_name=agent["name"],
                provider=agent["provider"],
                model=agent["model"]
            )

        logger.info("LLM configuration seeding completed successfully")

    except Exception as e:
        logger.error(f"Failed to seed LLM configurations: {e}")
        raise
    finally:
        # Disconnect
        await prisma_client.disconnect()
        logger.info("Disconnected from database")


if __name__ == "__main__":
    """Run the seeding script"""
    try:
        asyncio.run(seed_all_configs())
        logger.info("Seeding completed!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)

