"""
AI-powered conversation title generation using Gemini Flash
"""
import logging
import os
from typing import Optional
from src.infrastructure.llm.factory import LLMProviderFactory
from src.infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class TitleGenerator:
    """
    Generates concise, descriptive conversation titles using Gemini Flash
    """

    def __init__(self):
        """Initialize the title generator with Gemini Flash"""
        self._provider: Optional[LLMProvider] = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize Gemini Flash provider for title generation"""
        try:
            google_api_key = os.getenv("GOOGLE_API_KEY", "")

            if not google_api_key:
                logger.warning("GOOGLE_API_KEY not found. Title generation will use fallback.")
                return

            # Use Gemini Flash 2.0 for fast, low-cost title generation
            config = {
                "provider": "gemini",
                "model": "gemini-2.0-flash-exp",  # Latest Flash model, very cheap and fast
                "api_key": google_api_key,
            }

            self._provider = LLMProviderFactory.create(config)
            logger.info("Title generator initialized with Gemini Flash 2.0")

        except Exception as e:
            logger.error(f"Failed to initialize title generator: {e}")
            self._provider = None

    async def generate_title(self, user_query: str, max_length: int = 50) -> str:
        """
        Generate a concise conversation title based on the user's first query

        Args:
            user_query: The user's initial message
            max_length: Maximum length for the title (default: 50 chars)

        Returns:
            A concise, descriptive title
        """
        # Fallback if provider not available
        if not self._provider:
            return self._fallback_title(user_query, max_length)

        try:
            prompt = f"""Generate a very concise, descriptive title (max {max_length} characters) for a conversation that starts with this query:

"{user_query}"

Requirements:
- Maximum {max_length} characters
- No quotes or punctuation at start/end
- Descriptive and specific
- Professional tone
- Return ONLY the title, nothing else

Example queries and titles:
- "Show me all companies in California" → "California Companies"
- "Who are my top 10 contacts?" → "Top 10 Contacts"
- "hello" → "Quick Chat"
- "What are our Q4 revenue numbers?" → "Q4 Revenue Analysis"

Title:"""

            messages = [
                {"role": "user", "content": prompt}
            ]

            # Generate title with low temperature for consistency
            title = self._provider.chat(
                messages,
                temperature=0.3,
                max_tokens=30  # Keep it short
            )

            # Clean up the response
            title = title.strip().strip('"').strip("'").strip()

            # Ensure it's not too long
            if len(title) > max_length:
                title = title[:max_length].rsplit(' ', 1)[0]  # Cut at last word boundary

            # Validate it's not empty
            if not title or len(title) < 3:
                logger.warning(f"Generated title too short: '{title}', using fallback")
                return self._fallback_title(user_query, max_length)

            logger.info(f"Generated title: '{title}' for query: '{user_query[:50]}...'")
            return title

        except Exception as e:
            logger.error(f"Title generation failed: {e}, using fallback")
            return self._fallback_title(user_query, max_length)

    def _fallback_title(self, user_query: str, max_length: int) -> str:
        """
        Fallback title generation when AI is unavailable

        Args:
            user_query: The user's query
            max_length: Maximum length for the title

        Returns:
            A simple title based on the query text
        """
        # Take first sentence or first N characters
        title = user_query.split('.')[0].split('?')[0].split('!')[0].strip()

        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + '...'

        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]
        else:
            title = "New Conversation"

        return title


# Global singleton instance
_title_generator: Optional[TitleGenerator] = None


def get_title_generator() -> TitleGenerator:
    """Get or create the global title generator instance"""
    global _title_generator
    if _title_generator is None:
        _title_generator = TitleGenerator()
    return _title_generator
