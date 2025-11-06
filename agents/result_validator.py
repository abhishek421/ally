"""
ResultValidator - Validates extraction results with heuristic and semantic checks

This validator performs multi-level validation:
1. Heuristic validation (fast, rule-based)
2. Semantic validation (LLM-based, thorough)
3. Confidence calculation
4. Next action determination
"""
import logging
import json
import time
from typing import Dict, Any, List, Optional
from adapters.llm_provider import LLMProvider
from agents.models import (
    ValidationResult,
    ValidationIssue,
    SemanticValidation,
    NextAction
)
from agents.utils import (
    detect_query_type,
    detect_data_type,
    create_data_summary,
    score_reasoning_quality,
    score_data_quantity
)
from prompts.reactive_execution_prompts import SEMANTIC_VALIDATION_PROMPT


class ResultValidator:
    """
    Validates extraction results and provides actionable feedback

    Validation Levels:
    1. Heuristic - Fast, rule-based checks
    2. Semantic - LLM-based deep validation
    3. Confidence - Overall answer quality scoring
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize ResultValidator

        Args:
            llm_provider: LLM provider instance (optional, will create if None)
        """
        self._logger = logging.getLogger(__name__)

        # Set LLM provider for semantic validation
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            from config.settings import DATA_EXTRACTOR_CONFIG
            self.llm_provider = LLMProviderFactory.create(DATA_EXTRACTOR_CONFIG)

        self._logger.debug("ResultValidator initialized")

    async def validate(
        self,
        original_query: str,
        optimized_query: str,
        extracted_data: Dict[str, Any],
        reasoning_traces: Optional[List] = None,
        enable_semantic: bool = True
    ) -> ValidationResult:
        """
        Main validation entry point

        Args:
            original_query: Original user query
            optimized_query: Optimized query from QueryOptimizer
            extracted_data: Extracted data from DataExtractor
            reasoning_traces: Optional reasoning traces
            enable_semantic: Whether to run semantic validation (default: True)

        Returns:
            ValidationResult with comprehensive validation outcome
        """
        self._logger.info("Starting result validation")
        start_time = time.time()

        try:
            # Level 1: Fast heuristic checks
            heuristic_result = self._heuristic_validation(
                original_query, extracted_data
            )
            self._logger.debug(f"Heuristic validation: {len(heuristic_result['issues'])} issues found")

            # Level 2: LLM-based semantic validation (if enabled and data exists)
            semantic_result = None
            has_data = heuristic_result.get('has_data', False)

            if enable_semantic and has_data:
                semantic_result = await self._semantic_validation(
                    original_query, optimized_query, extracted_data
                )
                self._logger.debug(
                    f"Semantic validation: query_answered={semantic_result.query_answered}, "
                    f"should_accept={semantic_result.should_accept}"
                )
            elif enable_semantic and not has_data:
                self._logger.debug("Skipping semantic validation - no data to validate")

            # Level 3: Confidence calculation
            confidence_score = self._calculate_confidence(
                heuristic_result,
                semantic_result,
                extracted_data,
                reasoning_traces or []
            )
            self._logger.debug(f"Overall confidence: {confidence_score:.2f}")

            # Determine next action
            next_action = self._determine_next_action(
                heuristic_result,
                semantic_result,
                confidence_score
            )
            self._logger.info(f"Validation complete: next_action={next_action}")

            # Compile results
            validation_result = ValidationResult(
                is_sufficient=(
                    semantic_result.query_answered if semantic_result
                    else heuristic_result.get('has_data', False)
                ),
                confidence_score=confidence_score,
                heuristic_issues=heuristic_result.get('issues', []),
                semantic_analysis=semantic_result,
                recommendations=self._generate_recommendations(
                    heuristic_result,
                    semantic_result,
                    next_action
                ),
                next_action=next_action,
                metadata={
                    "validation_time_ms": int((time.time() - start_time) * 1000),
                    "semantic_enabled": enable_semantic,
                    "has_data": has_data
                }
            )

            return validation_result

        except Exception as e:
            self._logger.exception(f"Error in validation: {e}")
            # Return safe default on error
            return ValidationResult(
                is_sufficient=False,
                confidence_score=0.0,
                heuristic_issues=[
                    ValidationIssue(
                        severity="ERROR",
                        type="VALIDATION_ERROR",
                        message=f"Validation failed: {str(e)}",
                        recommendation="Retry validation or proceed without validation"
                    )
                ],
                semantic_analysis=None,
                recommendations=["Validation encountered an error, results may be unreliable"],
                next_action=NextAction.COMPLETE,
                metadata={"error": str(e)}
            )

    def _heuristic_validation(
        self,
        query: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fast rule-based validation checks

        Checks:
        1. Is data empty?
        2. Are there errors?
        3. Does data type match query type?
        4. Are there data quality issues?

        Args:
            query: Original query
            data: Extracted data

        Returns:
            Dictionary with validation results
        """
        issues = []

        # Check 1: Empty data
        has_data = any(
            len(v) > 0 if isinstance(v, list) else v is not None
            for k, v in data.items()
            if not k.startswith("_")
        )

        if not has_data:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    type="EMPTY_DATA",
                    message="No data was retrieved",
                    recommendation="Check if entities exist in database or refine search criteria"
                )
            )

        # Check 2: Errors in data
        if "_errors" in data and data["_errors"]:
            for error in data["_errors"]:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        type="TOOL_ERROR",
                        message=f"Tool {error['tool']} failed: {error['error']}",
                        recommendation="Retry with different parameters",
                        details=error
                    )
                )

        # Check 3: Query type vs data type mismatch
        query_type = detect_query_type(query)
        data_type = detect_data_type(data)

        if query_type == "COUNT" and data_type == "LIST":
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    type="TYPE_MISMATCH",
                    message="Query asks for count but returned list of items",
                    recommendation="Response formatter should count the items",
                    impact="User expects a number, not a list"
                )
            )

        # Check 4: Ambiguous results (too many)
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 50:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        type="TOO_MANY_RESULTS",
                        message=f"Retrieved {len(value)} {key}, query might be too broad",
                        recommendation=f"Consider filtering or asking for clarification",
                        impact="User might be overwhelmed with results"
                    )
                )

        # Check 5: Low confidence scores (if available)
        if "_confidence_scores" in data:
            low_confidence_tools = [
                tool for tool, score in data["_confidence_scores"].items()
                if score < 0.5
            ]
            if low_confidence_tools:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        type="LOW_CONFIDENCE",
                        message=f"Low confidence tools: {', '.join(low_confidence_tools)}",
                        recommendation="Review results carefully, consider refinement"
                    )
                )

        return {
            "passed": len([i for i in issues if i.severity == "ERROR"]) == 0,
            "has_data": has_data,
            "issues": issues
        }

    async def _semantic_validation(
        self,
        original_query: str,
        optimized_query: str,
        extracted_data: Dict[str, Any]
    ) -> SemanticValidation:
        """
        LLM-based deep validation

        Asks LLM:
        1. Is the query answered?
        2. Is the answer complete?
        3. Is the answer accurate?
        4. What's missing?

        Args:
            original_query: Original user query
            optimized_query: Optimized query
            extracted_data: Extracted data

        Returns:
            SemanticValidation object
        """
        self._logger.debug("Starting semantic validation with LLM")

        # Create data summary (truncated for token efficiency)
        data_summary = create_data_summary(extracted_data, max_length=800)

        # Create data sample (first few items for context)
        data_sample = self._create_data_sample(extracted_data, max_items=3)

        # Format prompt
        prompt = SEMANTIC_VALIDATION_PROMPT.format(
            original_query=original_query,
            optimized_query=optimized_query,
            data_summary=data_summary,
            data_sample=data_sample
        )

        # Call LLM
        messages = [
            {
                "role": "system",
                "content": "You are a data validation expert. Analyze if extracted data answers the user's query."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        try:
            llm_response = self.llm_provider.chat(messages, temperature=0.1)
            self._logger.debug(f"LLM response received: {len(llm_response)} chars")

            # Parse JSON response
            json_text = self._extract_json_from_response(llm_response)
            parsed = json.loads(json_text)

            # Convert to SemanticValidation model
            semantic_validation = SemanticValidation(
                query_answered=parsed.get("query_answered", False),
                completeness=parsed.get("completeness", 0.0),
                accuracy=parsed.get("accuracy", 0.0),
                relevance=parsed.get("relevance", 0.0),
                ambiguity_level=parsed.get("ambiguity_level", 0.0),
                missing_information=parsed.get("missing_information", []),
                data_quality_concerns=parsed.get("data_quality_concerns", []),
                should_accept=parsed.get("should_accept", False),
                next_step=parsed.get("next_step", "ACCEPT"),
                reasoning=parsed.get("reasoning", "No reasoning provided")
            )

            self._logger.debug(
                f"Semantic validation complete: "
                f"query_answered={semantic_validation.query_answered}, "
                f"completeness={semantic_validation.completeness:.2f}"
            )

            return semantic_validation

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM JSON response: {e}")
            self._logger.debug(f"Raw response: {llm_response}")
            # Return conservative default
            return SemanticValidation(
                query_answered=False,
                completeness=0.5,
                accuracy=0.5,
                relevance=0.5,
                ambiguity_level=0.5,
                missing_information=["Unable to validate - parsing error"],
                data_quality_concerns=["Validation failed"],
                should_accept=False,
                next_step="ACCEPT",
                reasoning=f"Validation parsing failed: {e}"
            )

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response (might be wrapped in code blocks)

        Args:
            response: Raw LLM response

        Returns:
            Extracted JSON string
        """
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            # Find the first newline after ```
            start_idx = response.find("\n") + 1
            # Find the closing ```
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()

        # If response doesn't start with {, try to find the JSON object
        if not response.startswith("{"):
            start_idx = response.find("{")
            if start_idx >= 0:
                response = response[start_idx:]

        return response

    def _create_data_sample(self, data: Dict[str, Any], max_items: int = 3) -> str:
        """
        Create a sample of data for LLM to analyze

        Args:
            data: Full data dictionary
            max_items: Maximum items per category

        Returns:
            JSON string with sample data
        """
        sample = {}

        for key, value in data.items():
            if key.startswith("_"):
                continue

            if isinstance(value, list) and len(value) > 0:
                # Take first max_items
                sample[key] = value[:max_items]
            elif value is not None:
                sample[key] = value

        return json.dumps(sample, indent=2, default=str)

    def _calculate_confidence(
        self,
        heuristic_result: Dict,
        semantic_result: Optional[SemanticValidation],
        extracted_data: Dict[str, Any],
        reasoning_traces: List
    ) -> float:
        """
        Calculate overall confidence score

        Factors:
        1. Heuristic checks passed (30%)
        2. Semantic validation scores (40%)
        3. Data quantity (15%)
        4. Reasoning quality (15%)

        Args:
            heuristic_result: Results from heuristic validation
            semantic_result: Results from semantic validation (optional)
            extracted_data: Extracted data
            reasoning_traces: Reasoning traces

        Returns:
            Overall confidence score 0.0-1.0
        """
        # Factor 1: Heuristic checks (30%)
        heuristic_score = 0.0
        if heuristic_result.get("passed"):
            heuristic_score = 1.0
        else:
            error_count = len([
                i for i in heuristic_result.get("issues", [])
                if i.severity == "ERROR"
            ])
            heuristic_score = max(0.0, 1.0 - (error_count * 0.5))  # Penalize errors more

        # Factor 2: Semantic scores (40%)
        semantic_score = 0.5  # Default if no semantic validation
        if semantic_result:
            semantic_score = (
                semantic_result.completeness * 0.4 +
                semantic_result.accuracy * 0.4 +
                (1.0 - semantic_result.ambiguity_level) * 0.2
            )

        # Factor 3: Data quantity (15%)
        data_score = score_data_quantity(extracted_data)

        # Special case: If no data at all, heavily penalize
        if not heuristic_result.get("has_data", False):
            data_score = 0.0

        # Factor 4: Reasoning quality (15%)
        reasoning_score = score_reasoning_quality(reasoning_traces) if reasoning_traces else 0.7

        # Weighted average
        confidence = (
            heuristic_score * 0.30 +
            semantic_score * 0.40 +
            data_score * 0.15 +
            reasoning_score * 0.15
        )

        return round(confidence, 2)

    def _determine_next_action(
        self,
        heuristic_result: Dict,
        semantic_result: Optional[SemanticValidation],
        confidence_score: float
    ) -> NextAction:
        """
        Determine what should happen next

        Decision Tree:
        - confidence >= 0.8 and query_answered -> COMPLETE
        - confidence >= 0.5 and query_answered -> COMPLETE (with caveats)
        - query not answered and has recommendations -> REFINE
        - query ambiguous or unclear -> CLARIFY
        - no data at all -> CLARIFY

        Args:
            heuristic_result: Heuristic validation results
            semantic_result: Semantic validation results (optional)
            confidence_score: Overall confidence score

        Returns:
            NextAction enum value
        """
        has_data = heuristic_result.get("has_data", False)

        # No data at all - need clarification or refinement
        if not has_data:
            return NextAction.CLARIFY

        # If we have semantic validation results, use them
        if semantic_result:
            # High confidence and query answered - we're done
            if confidence_score >= 0.8 and semantic_result.query_answered:
                return NextAction.COMPLETE

            # Medium confidence and query answered - accept with caveats
            if confidence_score >= 0.5 and semantic_result.query_answered:
                return NextAction.COMPLETE

            # Query not answered - check semantic recommendation
            if not semantic_result.query_answered:
                if semantic_result.next_step == "CLARIFY_QUERY":
                    return NextAction.CLARIFY
                elif semantic_result.next_step == "REFINE_SEARCH":
                    return NextAction.REFINE
                else:
                    return NextAction.REFINE

            # High ambiguity - need clarification
            if semantic_result.ambiguity_level > 0.7:
                return NextAction.CLARIFY

        # Fallback to heuristic-only decision
        if confidence_score >= 0.7:
            return NextAction.COMPLETE
        elif confidence_score >= 0.4:
            return NextAction.REFINE
        else:
            return NextAction.CLARIFY

    def _generate_recommendations(
        self,
        heuristic_result: Dict,
        semantic_result: Optional[SemanticValidation],
        next_action: NextAction
    ) -> List[str]:
        """
        Generate actionable recommendations

        Args:
            heuristic_result: Heuristic validation results
            semantic_result: Semantic validation results (optional)
            next_action: Determined next action

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Add heuristic recommendations
        for issue in heuristic_result.get("issues", []):
            if issue.recommendation:
                recommendations.append(issue.recommendation)

        # Add semantic recommendations
        if semantic_result and semantic_result.missing_information:
            for missing in semantic_result.missing_information[:3]:
                recommendations.append(f"Missing: {missing}")

        # Add action-specific recommendations
        if next_action == NextAction.REFINE:
            recommendations.append("Try refining search with more specific parameters")
        elif next_action == NextAction.CLARIFY:
            recommendations.append("Ask user for more specific information")

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations[:5]  # Limit to top 5
