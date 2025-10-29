# Application settings and configuration
import os
from dotenv import load_dotenv
from prompts import QUERY_OPTIMIZER_TEMPLATE

# Load variables from a .env file if present
load_dotenv()

# LLM Configuration (from environment; falls back to defaults if unset)
OPENAI_API_KEY=REDACTED
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")  # or "gpt-3.5-turbo"

# Prompt templates (imported from prompts module)
QUERY_OPTIMIZATION_TEMPLATE = QUERY_OPTIMIZER_TEMPLATE

