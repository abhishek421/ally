"""
ResponseFormatterAgent - Formats the extracted data into a professional markdown response
"""
from typing import Dict, Any, Optional
import logging
import json
import time
from adapters.llm_provider import LLMProvider
from config.settings import RESPONSE_FORMATTER_CONFIG


class ResponseFormatterAgent:
    """Agent that formats extracted data into a professional markdown response"""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize ResponseFormatterAgent

        Args:
            llm_provider: LLM provider instance (injected dependency)
                         If None, will be created from config
        """
        # Import template here to avoid circular imports
        from prompts.response_formatter_prompt import RESPONSE_FORMATTER_TEMPLATE

        # Use template directly (persona is now inlined in the template)
        self.template = RESPONSE_FORMATTER_TEMPLATE

        # Logger initialization
        self._logger = logging.getLogger(__name__)
        if not self._logger.handlers and not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
            )

        # Set LLM provider (injected or created from config)
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            self.llm_provider = LLMProviderFactory.create(RESPONSE_FORMATTER_CONFIG)

        self._logger.debug(f"ResponseFormatterAgent initialized with provider: {self.llm_provider}")

    def format(self, optimized_query: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the extracted data into a professional response

        Args:
            optimized_query: The optimized query from QueryOptimizerAgent
            extracted_data: The extracted data from DataExtractorAgent

        Returns:
            Dictionary containing:
            {
                "response": str,  # Formatted markdown response
                "data": dict,               # Original extracted data
                "metadata": dict            # Additional metadata (token count, processing time, etc.)
            }
        """
        self._logger.info("Starting response formatting")
        self._logger.debug(f"Optimized query: {optimized_query}")
        self._logger.debug(f"Extracted data keys: {list(extracted_data.keys())}")

        start_time = time.time()

        try:
            # Prepare extracted data as formatted JSON string
            extracted_data_str = json.dumps(extracted_data, indent=2, default=str)

            # Format prompt template
            prompt = self.template.format(
                optimized_query=optimized_query,
                extracted_data=extracted_data_str
            )

            self._logger.debug(f"Prompt prepared (length={len(prompt)})")

            # Prepare messages for LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional data analyst assistant that creates clear, well-structured markdown responses based on extracted data."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            # Call LLM to generate formatted response
            call_start = time.time()
            response = self.llm_provider.chat(messages, temperature=0.3)
            call_elapsed_ms = int((time.time() - call_start) * 1000)

            self._logger.info(f"LLM formatting completed in {call_elapsed_ms} ms")
            self._logger.debug(f"Generated response length: {len(response)} chars")

            # Clean up the response (remove any code block markers if present)
            response = self._clean_response(response)

            # Calculate total elapsed time
            total_elapsed_ms = int((time.time() - start_time) * 1000)

            # Prepare final response
            final_response = {
                "response": response,
                "data": extracted_data,
                "metadata": {
                    "processing_time_ms": total_elapsed_ms,
                    "llm_call_time_ms": call_elapsed_ms,
                    "response_length": len(response),
                    "data_sources_count": self._count_data_sources(extracted_data)
                }
            }

            self._logger.info(f"Response formatting completed in {total_elapsed_ms} ms")

            return final_response

        except Exception as e:
            self._logger.exception(f"Error in response formatting: {e}")
            # Return error response with data
            return {
                "response": self._create_error_response(str(e)),
                "data": extracted_data,
                "metadata": {
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "error": str(e)
                }
            }

    def _clean_response(self, response: str) -> str:
        """
        Clean up the markdown response by removing code block markers if present

        Args:
            response: Raw LLM response

        Returns:
            Cleaned markdown string
        """
        response = response.strip()

        # Remove markdown code blocks if the entire response is wrapped
        if response.startswith("```markdown") or response.startswith("```md"):
            # Find the first newline after the opening ```
            start_idx = response.find("\n") + 1
            # Find the closing ```
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()
        elif response.startswith("```"):
            # Generic code block
            start_idx = response.find("\n") + 1
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()

        return response

    def _count_data_sources(self, extracted_data: Dict[str, Any]) -> int:
        """
        Count the number of non-empty data sources in extracted data

        Args:
            extracted_data: Extracted data dictionary

        Returns:
            Count of non-empty data sources
        """
        count = 0

        # Count non-empty lists and non-null single values
        for key, value in extracted_data.items():
            if key.startswith("_"):  # Skip metadata keys like _errors
                continue

            if isinstance(value, list) and len(value) > 0:
                count += 1
            elif value is not None and not isinstance(value, list):
                count += 1

        return count

    def _create_error_response(self, error_message: str) -> str:
        """
        Create a user-friendly error response in markdown

        Args:
            error_message: Error message to display

        Returns:
            Markdown formatted error message
        """
        return f"""# Error Processing Response

I encountered an error while formatting the response:

**Error:** {error_message}

Please try again or contact support if the issue persists.

---
*If you have the raw data available, it has been included in the response for your reference.*
"""