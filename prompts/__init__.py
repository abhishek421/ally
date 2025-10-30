"""
Prompts module - Contains all prompt templates for the AI Analyst pipeline
"""

# Import prompt templates from their respective modules
from prompts.query_optimizer_prompt import QUERY_OPTIMIZER_TEMPLATE
from prompts.data_extractor_prompt import DATA_EXTRACTOR_TEMPLATE

__all__ = ['QUERY_OPTIMIZER_TEMPLATE', 'DATA_EXTRACTOR_TEMPLATE']

