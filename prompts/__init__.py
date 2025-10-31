"""
Prompts module - Contains all prompt templates for the AI Analyst pipeline
"""

# Import business analyst persona (core system context)
from prompts.business_analyst_persona import (
    BUSINESS_ANALYST_PERSONA,
    BUSINESS_ANALYST_SYSTEM_CONTEXT
)

# Import prompt templates from their respective modules
from prompts.query_optimizer_prompt import QUERY_OPTIMIZER_TEMPLATE
from prompts.data_extractor_prompt import DATA_EXTRACTOR_TEMPLATE
from prompts.response_formatter_prompt import RESPONSE_FORMATTER_TEMPLATE

__all__ = [
    'BUSINESS_ANALYST_PERSONA',
    'BUSINESS_ANALYST_SYSTEM_CONTEXT',
    'QUERY_OPTIMIZER_TEMPLATE',
    'DATA_EXTRACTOR_TEMPLATE',
    'RESPONSE_FORMATTER_TEMPLATE'
]

