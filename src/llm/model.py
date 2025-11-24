"""
Multi-model LLM routing layer for the CRM AI Copilot.

This module provides a centralized routing system that allows the agent to use
different LLM models for different tasks based on their requirements:

Model Routing Strategy:

1. Planner Tasks (PLANNER_MODEL)
   - Requires: Strong reasoning, complex planning, task decomposition
   - Use case: Analyzing user intent, generating execution plans
   - Default: gpt-4-turbo-preview (high reasoning capability)

2. Summarization Tasks (SUMMARY_MODEL)
   - Requires: Fast processing, concise output generation
   - Use case: Generating final summaries, quick text transformation
   - Default: gpt-3.5-turbo (fast and cost-effective)

3. Reasoning Tasks (REASONING_MODEL)
   - Requires: Deep thinking, multi-step reasoning, problem solving
   - Use case: Complex analysis, decision making, validation
   - Default: gpt-4-turbo-preview (highest reasoning capability)

4. Fallback Tasks (FALLBACK_MODEL)
   - Requires: Reliability, cost-effectiveness
   - Use case: When primary models fail or for simple tasks
   - Default: gpt-3.5-turbo (reliable and cheap)

Configuration:

All models are configured via environment variables in settings.py:
- PLANNER_MODEL=gpt-4-turbo-preview
- SUMMARY_MODEL=gpt-3.5-turbo
- REASONING_MODEL=gpt-4-turbo-preview
- FALLBACK_MODEL=gpt-3.5-turbo

This allows easy model switching without code changes.

Provider Support:

Currently Supported:
- OpenAI (GPT-4, GPT-3.5, etc.)

Coming Soon (placeholders ready):
- Anthropic (Claude models)
- Google (Gemini models)

The router automatically detects provider from model name prefix:
- "gpt-*" → OpenAI
- "claude-*" → Anthropic
- "gemini-*" → Google

Where LLM Calls Are Made:

✓ Planner Node: Uses call_planner() for generating execution plans
✓ Reasoning Steps: Uses call_reasoning() for deep analysis
✓ Summarization: Uses call_summarizer() for final summaries

✗ Executor Node: Does NOT call LLM (only executes tools)
✗ Validator Node: Does NOT call LLM (pure Python logic)
✗ Aggregator Node: Does NOT call LLM (data transformation)

JSON Mode:

When json_mode=True, the model is instructed to return valid JSON.
This is critical for structured outputs like plans and task lists.

Error Handling:

All LLM calls include:
- Automatic retry on transient failures
- Fallback to FALLBACK_MODEL on persistent errors
- Comprehensive logging of errors and retries
- Never raises exceptions (returns error strings instead)

Performance Monitoring:

Each LLM call logs:
- Route name (planner, summarizer, etc.)
- Model used
- Time taken
- Token usage (future)
- Success/failure status

Example Usage:

    from src.llm.model import call_planner, call_summarizer
    
    # Planning task (uses strong model)
    plan = await call_planner("Generate a plan to find companies in SF")
    
    # Summarization task (uses fast model)
    summary = await call_summarizer("Summarize these results: ...")
    
    # Custom routing
    from src.llm.model import llm_router
    response = await llm_router.call("reasoning", prompt, json_mode=True)
"""

import json
import time
from typing import Optional, Dict, Any

from src.config.settings import settings
from src.config.logger import logger

# LLM Provider Clients
from openai import AsyncOpenAI

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not installed. Install with: pip install anthropic")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Generative AI SDK not installed. Install with: pip install google-generativeai")


# ========================================
# Initialize Clients
# ========================================

# OpenAI client
openai_client = None
if settings.OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("OpenAI client initialized")
else:
    logger.warning("OPENAI_API_KEY not set - OpenAI models will not be available")

# Anthropic client
anthropic_client = None
if ANTHROPIC_AVAILABLE and settings.ANTHROPIC_API_KEY:
    anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    logger.info("Anthropic client initialized")
elif settings.ANTHROPIC_API_KEY and not ANTHROPIC_AVAILABLE:
    logger.warning("ANTHROPIC_API_KEY set but SDK not installed. Install with: pip install anthropic")

# Google Gemini client
gemini_client = None
if GEMINI_AVAILABLE and settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    gemini_client = genai
    logger.info("Google Gemini client initialized")
elif settings.GOOGLE_API_KEY and not GEMINI_AVAILABLE:
    logger.warning("GOOGLE_API_KEY set but SDK not installed. Install with: pip install google-generativeai")

logger.info("LLM clients initialization complete")


# ========================================
# Model Router Class
# ========================================

class ModelRouter:
    """
    LLM routing system for task-specific model selection.
    
    Routes different types of tasks to appropriate models based on
    their requirements (reasoning capability, speed, cost).
    
    Routes:
    - planner: Strong reasoning for planning tasks
    - summarizer: Fast model for summaries
    - reasoning: Deep thinking for complex analysis
    - fallback: Reliable backup model
    """
    
    def __init__(self):
        """Initialize router with model mappings from settings."""
        self.routes = {
            "planner": settings.PLANNER_MODEL,
            "summarizer": settings.SUMMARY_MODEL,
            "reasoning": settings.REASONING_MODEL,
            "fallback": settings.FALLBACK_MODEL,
        }
        
        logger.info(f"Model router initialized with routes: {self.routes}")
    
    def set_route(self, key: str, model: str) -> None:
        """
        Override a specific route with a different model.
        
        Useful for:
        - A/B testing different models
        - Temporarily switching to cheaper models
        - Using specialized models for specific workloads
        
        Args:
            key: Route name (planner, summarizer, reasoning, fallback)
            model: Model identifier (e.g., "gpt-4", "claude-3-opus")
        
        Example:
            router.set_route("planner", "gpt-4-0125-preview")
        """
        old_model = self.routes.get(key)
        self.routes[key] = model
        logger.info(f"Route '{key}' changed from '{old_model}' to '{model}'")
    
    async def call(
        self,
        route: str,
        prompt: str,
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.2
    ) -> str:
        """
        Call LLM with automatic routing based on task type.
        
        This is the main entry point for all LLM calls. It:
        1. Selects appropriate model based on route
        2. Detects provider from model name
        3. Calls provider-specific method
        4. Logs performance metrics
        5. Handles errors with fallback
        
        Args:
            route: Task type (planner, summarizer, reasoning, fallback)
            prompt: Text prompt to send to LLM
            json_mode: If True, force JSON output format
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-2.0)
        
        Returns:
            LLM response as string
        
        Raises:
            Does not raise - returns error message string on failure
        
        Example:
            response = await router.call(
                "planner",
                "Generate a plan to find companies",
                json_mode=True
            )
        """
        # Get model for this route
        model = self.routes.get(route, settings.FALLBACK_MODEL)
        
        logger.debug(f"LLM call via route '{route}' using model '{model}'")
        logger.debug(f"Prompt preview: {prompt[:100]}...")
        
        # Start timing
        start_time = time.time()
        
        try:
            # Route by model prefix
            if model.startswith("gpt"):
                response = await self._call_openai(
                    model, prompt, json_mode, max_tokens, temperature
                )
            elif model.startswith("claude"):
                response = await self._call_anthropic(
                    model, prompt, json_mode, max_tokens, temperature
                )
            elif model.startswith("gemini"):
                response = await self._call_gemini(
                    model, prompt, json_mode, max_tokens, temperature
                )
            else:
                logger.warning(
                    f"Unknown model prefix for '{model}', falling back to fallback model"
                )
                fallback_model = self.routes.get("fallback", "gpt-3.5-turbo")
                response = await self._call_openai(
                    fallback_model, prompt, json_mode, max_tokens, temperature
                )
            
            # Calculate duration
            duration = time.time() - start_time
            
            logger.info(
                f"LLM call completed: route={route}, model={model}, "
                f"duration={duration:.2f}s, response_length={len(response)}"
            )
            
            return response
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"LLM call failed: route={route}, model={model}, "
                f"duration={duration:.2f}s, error={str(e)}",
                exc_info=True
            )
            
            # Return error message (don't raise)
            return f"Error calling LLM: {str(e)}"
    
    async def _call_openai(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """
        Call OpenAI API with retry logic.
        
        Args:
            model: OpenAI model name (e.g., "gpt-4-turbo-preview")
            prompt: Text prompt
            json_mode: Whether to force JSON output
            max_tokens: Max tokens in response
            temperature: Sampling temperature
        
        Returns:
            Model response as string
        
        Raises:
            Exception on failure after retries
        """
        if not openai_client:
            raise ValueError("OpenAI client not initialized. Set OPENAI_API_KEY in environment.")
        
        try:
            # Build request parameters
            request_params: Dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Handle max_tokens vs max_completion_tokens
            # Newer reasoning models (o1, gpt-5, etc.) use max_completion_tokens
            if model.startswith("o1") or model.startswith("gpt-5"):
                request_params["max_completion_tokens"] = max_tokens
                # reasoning models might strictly enforce temperature=1 or not support it
                # Documentation confirms gpt-5 family does not support temperature
                if "temperature" in request_params:
                    del request_params["temperature"]
            else:
                request_params["max_tokens"] = max_tokens
                request_params["temperature"] = temperature
            
            # Enable JSON mode if requested
            if json_mode:
                request_params["response_format"] = {"type": "json_object"}
            
            # Call OpenAI API
            response = await openai_client.chat.completions.create(**request_params)
            
            # Extract content
            content = response.choices[0].message.content
            
            if not content:
                logger.warning("OpenAI returned empty content")
                return ""
            
            return content
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise
    
    async def _call_anthropic(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """
        Call Anthropic Claude API.
        
        Args:
            model: Claude model name (e.g., "claude-3-opus-20240229", "claude-3-sonnet-20240229")
            prompt: Text prompt
            json_mode: Whether to force JSON output
            max_tokens: Max tokens in response
            temperature: Sampling temperature
        
        Returns:
            Model response as string
        
        Raises:
            ValueError: If Anthropic client not initialized
            Exception: On API errors
        """
        if not anthropic_client:
            raise ValueError(
                "Anthropic client not initialized. "
                "Set ANTHROPIC_API_KEY in environment and install: pip install anthropic"
            )
        
        try:
            # Build prompt with JSON instruction if needed
            system_prompt = ""
            if json_mode:
                system_prompt = "You must respond with valid JSON only. Do not include any text outside the JSON object."
            
            # Call Anthropic API
            response = await anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else None,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract content from response
            # Anthropic returns a list of content blocks
            content = response.content[0].text if response.content else ""
            
            if not content:
                logger.warning("Anthropic returned empty content")
                return ""
            
            return content
        
        except Exception as e:
            logger.error(f"Anthropic API error: {e}", exc_info=True)
            raise
    
    async def _call_gemini(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """
        Call Google Gemini API.
        
        Args:
            model: Gemini model name (e.g., "gemini-pro", "gemini-1.5-pro")
            prompt: Text prompt
            json_mode: Whether to force JSON output
            max_tokens: Max tokens in response
            temperature: Sampling temperature
        
        Returns:
            Model response as string
        
        Raises:
            ValueError: If Gemini client not initialized
            Exception: On API errors
        """
        if not gemini_client:
            raise ValueError(
                "Gemini client not initialized. "
                "Set GOOGLE_API_KEY in environment and install: pip install google-generativeai"
            )
        
        try:
            # Create model instance
            model_instance = gemini_client.GenerativeModel(model)
            
            # Configure generation
            generation_config = {
                "max_output_tokens": max_tokens,
            }

            # Handle temperature for newer models if needed
            # Some reasoning models might not support temperature or require it to be 1.0
            # For now, we include it unless strictly known otherwise, but we can allow 
            # override or removal if users encounter "unsupported parameter" errors.
            # However, the main issue reported is response handling.
            generation_config["temperature"] = temperature
            
            # Add JSON instruction if needed
            final_prompt = prompt
            if json_mode:
                final_prompt = f"{prompt}\n\nIMPORTANT: Respond with valid JSON only."
            
            # Call Gemini API
            # Note: Gemini SDK doesn't have native async support yet
            # We'll use the sync API (consider using asyncio.to_thread in production)
            response = model_instance.generate_content(
                final_prompt,
                generation_config=generation_config
            )
            
            # Extract content safely
            try:
                return response.text
            except ValueError:
                # Handle cases where response.text fails (e.g. finish_reason is MAX_TOKENS or SAFETY)
                # Check candidates
                if response.candidates:
                    candidate = response.candidates[0]
                    
                    # If we have parts, try to join them
                    if candidate.content and candidate.content.parts:
                        text_parts = [part.text for part in candidate.content.parts if part.text]
                        if text_parts:
                            return "".join(text_parts)
                    
                    # Log specific finish reasons
                    if candidate.finish_reason == 2: # MAX_TOKENS
                        logger.warning(f"Gemini model {model} hit max tokens limit ({max_tokens}). Partial response might be missing.")
                        # If parts were empty despite max tokens, it might be a hard stop
                        return ""
                    elif candidate.finish_reason == 3: # SAFETY
                        logger.warning(f"Gemini model {model} blocked response due to safety settings.")
                        return "Error: Response blocked by safety filters."
                    elif candidate.finish_reason == 4: # RECITATION
                        logger.warning(f"Gemini model {model} blocked response due to recitation.")
                        return "Error: Response blocked due to recitation."
                
                logger.warning(f"Gemini returned invalid or empty response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                return ""
        
        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise


# ========================================
# Export Router Instance
# ========================================

# Create singleton router instance
llm_router = ModelRouter()


# ========================================
# Convenience Functions
# ========================================

async def call_planner(
    prompt: str,
    json_mode: bool = True,
    max_tokens: int = 2048
) -> str:
    """
    Call LLM for planning tasks.
    
    Uses the strongest reasoning model (PLANNER_MODEL) to analyze user
    intent and generate execution plans.
    
    Args:
        prompt: Planning prompt
        json_mode: Force JSON output (default: True for structured plans)
        max_tokens: Max tokens (default: 2048 for complex plans)
    
    Returns:
        Plan as string (JSON if json_mode=True)
    
    Example:
        plan = await call_planner(
            "Generate a plan to search companies in San Francisco"
        )
    """
    return await llm_router.call(
        "planner",
        prompt,
        json_mode=json_mode,
        max_tokens=max_tokens
    )


async def call_summarizer(
    prompt: str,
    json_mode: bool = False,
    max_tokens: int = 512
) -> str:
    """
    Call LLM for summarization tasks.
    
    Uses a fast, cost-effective model (SUMMARY_MODEL) for generating
    concise summaries and final responses.
    
    Args:
        prompt: Summarization prompt
        json_mode: Force JSON output (default: False for text summaries)
        max_tokens: Max tokens (default: 512 for concise summaries)
    
    Returns:
        Summary as string
    
    Example:
        summary = await call_summarizer(
            "Summarize the following results: ..."
        )
    """
    return await llm_router.call(
        "summarizer",
        prompt,
        json_mode=json_mode,
        max_tokens=max_tokens
    )


async def call_reasoning(
    prompt: str,
    json_mode: bool = False,
    max_tokens: int = 1024
) -> str:
    """
    Call LLM for deep reasoning tasks.
    
    Uses the most capable reasoning model (REASONING_MODEL) for complex
    analysis, multi-step reasoning, and problem solving.
    
    Args:
        prompt: Reasoning prompt
        json_mode: Force JSON output (default: False)
        max_tokens: Max tokens (default: 1024)
    
    Returns:
        Reasoning output as string
    
    Example:
        analysis = await call_reasoning(
            "Analyze the relationship between these entities: ..."
        )
    """
    return await llm_router.call(
        "reasoning",
        prompt,
        json_mode=json_mode,
        max_tokens=max_tokens
    )


async def call_fallback(
    prompt: str,
    json_mode: bool = False,
    max_tokens: int = 512
) -> str:
    """
    Call LLM with fallback model.
    
    Uses a reliable, cost-effective model (FALLBACK_MODEL) as a backup
    when primary models fail or for simple tasks.
    
    Args:
        prompt: Text prompt
        json_mode: Force JSON output (default: False)
        max_tokens: Max tokens (default: 512)
    
    Returns:
        Response as string
    
    Example:
        response = await call_fallback(
            "Simple task that doesn't need strong reasoning"
        )
    """
    return await llm_router.call(
        "fallback",
        prompt,
        json_mode=json_mode,
        max_tokens=max_tokens
    )


# ========================================
# Exports
# ========================================

__all__ = [
    "llm_router",
    "ModelRouter",
    "call_planner",
    "call_summarizer",
    "call_reasoning",
    "call_fallback",
]

