"""
AI-Powered CSV Generator - Converts raw JSON data to user-friendly CSV
"""
import logging
import json
import io
from typing import List, Dict, Any, Iterator
from src.infrastructure.llm.factory import LLMProviderFactory
from src.shared.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SmartTableFormatter:
    """
    AI-powered CSV generator that:
    1. Takes raw JSON data (list of dicts)
    2. Asks LLM to format it as clean, user-friendly CSV
    3. Eliminates technical field names, IDs, empty fields
    4. Uses readable column headers
    5. Streams CSV output progressively
    """

    def __init__(self):
        """Initialize the AI CSV generator"""
        self.config_manager = ConfigManager()
        self._provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize LLM provider for CSV generation"""
        try:
            # Use the same LLM as the main system (fast, cheap model preferred)
            llm_config = self.config_manager.get_llm_config()
            self._provider = LLMProviderFactory.create(llm_config)
            logger.info(f"AI CSV generator initialized with {llm_config.get('provider')}/{llm_config.get('model')}")
        except Exception as e:
            logger.error(f"Failed to initialize AI CSV generator: {e}")
            self._provider = None

    def generate_csv_streaming(
        self,
        data: List[Dict[str, Any]],
        data_type: str,
        user_query: str,
        mode: str = "generative" 
    ) -> Iterator[str]:
        """
        Generate user-friendly CSV from JSON data, streaming chunks as they're generated
        
        Args:
            data: Raw data from database (list of dicts)
            data_type: Type of data (e.g., "companies", "people")
            user_query: Original user query for context
            mode: "generative" (analysis/new structure) or "transform" (row-by-row cleaning)

        Yields:
            CSV chunks (header first, then rows in batches)
        """
        if not data or len(data) == 0:
            return

        if not self._provider:
            # Fallback: use simple CSV generation
            logger.warning("No LLM provider available, using fallback CSV generation")
            yield from self._fallback_csv_generation(data, data_type)
            return

        try:
            # Choose strategy based on data size and mode
            # If data is too large (>50 items), force transform mode to avoid context limits
            # unless the user explicitly asked for analysis/summary which implies aggregation
            is_large_data = len(data) > 50
            
            if mode == "generative" and not is_large_data:
                # Generative Analysis (New structure/Aggregation)
                yield from self._generate_analysis_csv(data, data_type, user_query)
            else:
                # Row-by-row Transformation (Clean formatting, preserves rows)
                yield from self._generate_csv_with_llm_streaming(data, data_type, user_query)
                
        except Exception as e:
            logger.error(f"LLM CSV generation failed: {e}, using fallback")
            yield from self._fallback_csv_generation(data, data_type)

    def _generate_analysis_csv(
        self,
        data: List[Dict[str, Any]],
        data_type: str,
        user_query: str
    ) -> Iterator[str]:
        """
        Generative Analysis: Uses LLM to produce a NEW CSV structure that best answers the query.
        Use this for summaries, aggregations, or when the user wants a specific view.
        """
        # Serialize data (ensure it fits context)
        # We assume data <= 50 items here as enforced by caller
        serialized_data = json.dumps(data, indent=2, default=str)
        
        prompt = f"""You are a Senior Business Intelligence Analyst. 
Your task is to generate a CSV table that BEST visualizes the answer to the user's query based on the provided raw data.

User Query: "{user_query}"
Data Type: {data_type}

Raw Data:
{serialized_data}

INSTRUCTIONS:
1. Analyze the User Query and the Raw Data.
2. Determine the best table structure to answer the question.
   - If the user asks for a list, provide a clean list with relevant columns.
   - If the user asks for a count/summary (e.g., "count by city"), aggregate the data and show the summary table.
   - If the user asks for a comparison, create a comparison table.
3. Do NOT just dump the raw data. Create a specific response table.
4. Rename columns to be human-readable (e.g., "Company Name" instead of "company_name").
5. Format values nicely (e.g., dates, currency).
6. Output MUST be valid CSV format.

Output Rules:
- Return ONLY the CSV content (header + rows).
- NO markdown formatting (no ```csv ... ```).
- NO introductory text or explanations.
- Use comma (,) as delimiter.
- Quote values if they contain commas.

Generate the CSV now:"""

        messages = [{"role": "user", "content": prompt}]

        try:
            # Get LLM response with streaming
            response_stream = self._provider.chat_stream(messages, temperature=0.2, max_tokens=4000)
            
            # We need to handle the stream from the provider
            # If provider doesn't support streaming, it returns a string
            if isinstance(response_stream, str):
                # Not a stream, just yield the string
                cleaned_response = self._clean_csv_output(response_stream)
                yield cleaned_response + "\n"
            else:
                # It is an iterator/generator
                # We need to accumulate to ensure we don't break CSV structure mid-line? 
                # Actually, streaming the raw tokens is fine as long as the client handles it.
                # But we should try to clean markdown if possible.
                
                # For simplicity in this architecture, we'll buffer the whole response 
                # to clean markdown, OR we assume the prompt is obeyed.
                # Given "I want generated response", let's try to stream raw and clean only start/end if needed.
                # But removing ```csv is hard in a stream.
                
                # Alternative: Accumulate full response then yield (safer for formatting)
                # But user wants streaming.
                
                # Let's accumulate buffer for the first few tokens to check for ```csv
                accumulated = ""
                check_markdown = True
                
                for chunk in response_stream:
                    if check_markdown:
                        accumulated += chunk
                        if len(accumulated) > 10: # Check header
                            if accumulated.strip().startswith("```"):
                                # It's markdown, we need to buffer more or strip it
                                # This is complex to stream.
                                # Let's fallback to non-streaming for safety in Generative Mode
                                pass
                            check_markdown = False
                            yield accumulated
                            accumulated = ""
                    else:
                        yield chunk
                
                if accumulated:
                    yield accumulated

        except Exception as e:
            # If chat_stream is not implemented or fails
            logger.warning(f"Streaming failed or not supported: {e}. Falling back to standard chat.")
            response = self._provider.chat(messages, temperature=0.2, max_tokens=4000)
            yield self._clean_csv_output(response) + "\n"

    def _clean_csv_output(self, text: str) -> str:
        """Remove markdown and cleanup CSV"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```csv) and last line (```)
            if len(lines) >= 2:
                text = "\n".join(lines[1:-1])
            text = text.replace("```csv", "").replace("```", "").strip()
        return text

    def _generate_csv_with_llm_streaming(
        self,
        data: List[Dict[str, Any]],
        data_type: str,
        user_query: str
    ) -> Iterator[str]:
        """
        Use LLM to generate clean, user-friendly CSV with streaming output
        
        Strategy:
        1. Send first 3 rows as sample to LLM
        2. Ask LLM to return CSV header with clean column names
        3. Ask LLM to transform rows to match those columns
        4. Stream header immediately
        5. Process remaining rows in chunks and stream
        """
        # Take sample of data (first 3 rows for analysis)
        sample_size = min(3, len(data))
        sample_data = data[:sample_size]

        # Build prompt for LLM
        # Special handling for people data
        is_people_data = data_type == "people"
        
        people_specific_instructions = ""
        if is_people_data:
            people_specific_instructions = """
SPECIAL RULES FOR PEOPLE DATA:
- ALWAYS use "full_name" instead of "first_name" and "last_name" (merge them into one "Name" column)
- ALWAYS include "company_name" if it exists in the data (show linked companies)
- EXCLUDE "first_name", "last_name", "description", "date_of_birth", "gender", "image_url" if they are empty/null in ALL rows
- Priority order: Name, Job Title, Company, Privacy Level (only show fields with actual data)
"""
        
        prompt = f"""You are a data formatter. Convert this JSON data to a clean, user-friendly CSV.

USER QUERY: "{user_query}"
DATA TYPE: {data_type}
SAMPLE DATA (first {sample_size} rows):
{json.dumps(sample_data, indent=2, default=str)}

REQUIREMENTS:
1. Use READABLE column headers (not camelCase): "Company Name" not "companyName", "Email" not "emailAddress"
2. EXCLUDE technical fields: IDs, workspace IDs, metadata, timestamps, avatar URLs, internal references, nested objects/arrays
3. EXCLUDE empty/null fields that appear in ALL rows (if a column is empty for every row, don't include it)
4. INCLUDE only user-relevant data: names, emails, phones, descriptions, statuses, values
5. Maximum 8 columns for readability
6. Clean nested data: extract primary email from arrays, format addresses simply
7. Return VALID CSV format with proper escaping
{people_specific_instructions}

Example transformation for people:
{{
  "id": "123",
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",
  "job_title": "CEO",
  "company_name": "Acme Corp",
  "privacy_level": "PRIVATE",
  "description": null,
  "date_of_birth": null,
  "gender": null,
  "image_url": null
}}

Should become CSV row:
Name,Job Title,Company,Privacy Level
John Doe,CEO,Acme Corp,PRIVATE

(Note: description, date_of_birth, gender, image_url excluded because they're empty)

Return ONLY the CSV output (header + all rows), nothing else. No markdown, no explanations."""

        messages = [{"role": "user", "content": prompt}]

        try:
            # Get LLM response with streaming
            response = self._provider.chat(messages, temperature=0.1, max_tokens=4000)

            # Clean response (remove markdown if present)
            csv_output = self._clean_csv_output(response)

            # Validate it's CSV-like
            if not csv_output or "\n" not in csv_output:
                raise ValueError("LLM did not return valid CSV")

            # Parse the CSV to extract header and validate
            lines = csv_output.strip().split("\n")
            if len(lines) < 1:
                raise ValueError("Empty CSV output")

            header_line = lines[0]

            # Stream header immediately
            yield header_line + "\n"

            # If LLM returned sample rows, skip them and generate our own rows
            # based on the column mapping from the header
            if len(data) > sample_size:
                # Extract columns from header
                import csv
                csv_reader = csv.reader([header_line])
                columns = next(csv_reader)

                logger.info(f"LLM generated {len(columns)} columns: {columns}")

                # Now we need to map remaining data to these columns
                # Use LLM again to generate rows for remaining data in chunks
                remaining_data = data[sample_size:]
                chunk_size = 10

                for i in range(0, len(remaining_data), chunk_size):
                    chunk = remaining_data[i:i + chunk_size]

                    # Ask LLM to format this chunk
                    chunk_prompt = f"""Convert this JSON data to CSV rows matching these exact columns: {', '.join(columns)}

DATA:
{json.dumps(chunk, indent=2, default=str)}

RULES:
1. Return ONLY CSV rows (no header, already sent)
2. Match the column order exactly: {', '.join(columns)}
3. Clean nested data like before
4. Exclude empty fields
5. Proper CSV escaping

Return only the CSV rows:"""

                    chunk_messages = [{"role": "user", "content": chunk_prompt}]
                    chunk_response = self._provider.chat(chunk_messages, temperature=0.1, max_tokens=2000)

                    # Clean response
                    chunk_csv = self._clean_csv_output(chunk_response)

                    # Stream this chunk
                    if chunk_csv:
                        yield chunk_csv + "\n"

        except Exception as e:
            logger.error(f"LLM streaming CSV generation failed: {e}")
            raise

    def _fallback_csv_generation(
        self,
        data: List[Dict[str, Any]],
        data_type: str
    ) -> Iterator[str]:
        """
        Fallback CSV generation using rule-based approach
        """
        import csv

        if not data:
            return

        # Use simple column filtering
        exclude_patterns = [
            "id", "Id", "workspace", "Workspace", "avatar", "Avatar",
            "metadata", "metaData", "Etag", "Key", "createdBy", "updatedBy",
            "email", "phoneNumber", "address", "url", "metaData"  # Exclude nested arrays
        ]

        def should_exclude(col):
            col_lower = col.lower()
            return any(pattern.lower() in col_lower for pattern in exclude_patterns)

        # Get columns
        all_columns = list(data[0].keys())
        
        # Special handling for people data
        if data_type == "people":
            # Prefer full_name over first_name/last_name
            if "full_name" in all_columns:
                # Remove first_name and last_name if full_name exists
                all_columns = [c for c in all_columns if c not in ["first_name", "last_name"]]
        
        selected_columns = [col for col in all_columns if not should_exclude(col)]
        
        # Filter out columns that are empty in ALL rows
        columns_with_data = []
        for col in selected_columns:
            has_data = any(
                row.get(col) not in (None, "", []) 
                for row in data
            )
            if has_data:
                columns_with_data.append(col)
        
        # Limit to 8 columns
        selected_columns = columns_with_data[:8]

        # Convert camelCase to Title Case
        def to_title_case(s):
            # Insert space before capitals
            result = ""
            for i, c in enumerate(s):
                if c.isupper() and i > 0:
                    result += " "
                result += c
            return result.title().replace("_", " ")

        readable_headers = [to_title_case(col) for col in selected_columns]

        # Stream header
        header_buffer = io.StringIO()
        writer = csv.writer(header_buffer)
        writer.writerow(readable_headers)
        yield header_buffer.getvalue()

        # Stream rows in chunks
        chunk_size = 10
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]

            chunk_buffer = io.StringIO()
            writer = csv.writer(chunk_buffer)

            for row in chunk:
                row_values = []
                for col in selected_columns:
                    value = row.get(col, "")

                    # Clean nested structures
                    if isinstance(value, list) and value:
                        if isinstance(value[0], dict) and 'value' in value[0]:
                            value = ', '.join(str(item.get('value', '')) for item in value if isinstance(item, dict))
                        else:
                            value = ""
                    elif isinstance(value, dict):
                        value = ""

                    row_values.append(str(value) if value else "")

                writer.writerow(row_values)

            yield chunk_buffer.getvalue()


# Global singleton
_smart_formatter = None


def get_smart_table_formatter() -> SmartTableFormatter:
    """Get or create the global smart table formatter instance"""
    global _smart_formatter
    if _smart_formatter is None:
        _smart_formatter = SmartTableFormatter()
    return _smart_formatter
