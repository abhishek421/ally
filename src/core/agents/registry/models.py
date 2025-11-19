"""
Data models for reactive execution system

These models support the ReAct (Reasoning + Acting) pattern for dynamic tool execution.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class DecisionType(str, Enum):
    """Types of decisions the THINK phase can make"""
    SUFFICIENT = "SUFFICIENT"  # Have enough data, stop execution
    EXECUTE_TOOL = "EXECUTE_TOOL"  # Need to execute another tool
    CLARIFY = "CLARIFY"  # Need user clarification


class NextAction(str, Enum):
    """Actions the validator can recommend"""
    COMPLETE = "COMPLETE"  # Accept results and proceed
    REFINE = "REFINE"  # Retry with refinement
    CLARIFY = "CLARIFY"  # Ask user for clarification


class ProgressAssessment(str, Enum):
    """Assessment of execution progress"""
    GOOD = "good"  # Making good progress
    OK = "ok"  # Making some progress
    POOR = "poor"  # Not making much progress
    STUCK = "stuck"  # Not making any progress, might be looping


class ToolSpec(BaseModel):
    """Specification for a tool to execute"""
    tool: str = Field(..., description="Tool name (company|people|email|interaction|group|workspace)")
    query_type: str = Field(..., description="Query type (search|get_by_id|list|analytics)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for tool execution")
    expected_outcome: str = Field(..., description="What we hope to achieve with this tool")
    fallback_plan: Optional[str] = Field(None, description="What to do if tool fails or returns no results")


class ReasoningTrace(BaseModel):
    """A single reasoning trace entry from the THINK phase"""
    iteration: int = Field(..., description="Which iteration this trace is from")
    decision: DecisionType = Field(..., description="Decision made")
    reasoning: str = Field(..., description="Detailed explanation of the decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this decision")
    tool_spec: Optional[ToolSpec] = Field(None, description="Tool specification if decision is EXECUTE_TOOL")
    clarification_question: Optional[str] = Field(None, description="Question if decision is CLARIFY")
    clarification_reason: Optional[str] = Field(None, description="Why clarification is needed")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Observation(BaseModel):
    """What we learned from executing a tool"""
    tool: str = Field(..., description="Tool that was executed")
    success: bool = Field(..., description="Whether tool execution succeeded")
    result_count: int = Field(..., description="Number of results returned")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in tool result")
    learned: List[str] = Field(default_factory=list, description="Facts learned from this result")
    still_missing: List[str] = Field(default_factory=list, description="Information still missing")
    data_quality_issues: List[str] = Field(default_factory=list, description="Quality issues detected")
    relevance: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance to original query")
    new_questions: List[str] = Field(default_factory=list, description="New questions raised by this result")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Reflection(BaseModel):
    """Reflection on whether to continue execution"""
    should_continue: bool = Field(..., description="Whether to continue executing tools")
    reason: str = Field(..., description="Explanation of why to continue or stop")
    progress_assessment: ProgressAssessment = Field(..., description="Assessment of progress")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for next steps")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ToolCall(BaseModel):
    """Record of a tool execution"""
    tool_name: str
    query_type: str
    params: Dict[str, Any]
    result: Optional[Any] = None  # ToolResult object
    expected_outcome: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ExecutionState(BaseModel):
    """
    State maintained throughout reactive execution

    This state object is passed through each phase of the ReAct loop
    and accumulates information about the execution.
    """
    # Query context
    query: str = Field(..., description="Original optimized query")
    workspace_id: str = Field(..., description="Workspace identifier")
    user_id: str = Field(..., description="User identifier")

    # Goal tracking
    success_criteria: Dict[str, Any] = Field(default_factory=dict, description="Criteria for successful completion")
    original_intent: str = Field(..., description="Original query intent")

    # Execution tracking
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tools executed so far")
    observations: List[Observation] = Field(default_factory=list, description="Observations from tool results")
    reasoning_traces: List[ReasoningTrace] = Field(default_factory=list, description="Reasoning decisions")

    # Data collection
    collected_data: Dict[str, Any] = Field(default_factory=dict, description="Data collected from tools")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence per tool")

    # Loop control
    iteration: int = Field(default=0, description="Current iteration number")
    max_iterations: int = Field(default=5, description="Maximum iterations allowed")
    should_continue: bool = Field(default=True, description="Whether to continue loop")

    # Refinement (for retry loops from validator)
    refinement_feedback: Optional[Dict] = Field(None, description="Feedback from validator for refinement")
    
    # Context (for reference resolution)
    context_messages: Optional[List[Dict[str, Any]]] = Field(None, description="Previous conversation messages for context")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationIssue(BaseModel):
    """An issue detected during validation"""
    severity: str = Field(..., description="ERROR|WARNING|INFO")
    type: str = Field(..., description="Issue type code")
    message: str = Field(..., description="Human-readable issue description")
    recommendation: str = Field(..., description="Actionable recommendation")
    impact: Optional[str] = Field(None, description="Impact of this issue")
    details: Optional[Any] = Field(None, description="Additional details")


class SemanticValidation(BaseModel):
    """Results from LLM-based semantic validation"""
    query_answered: bool = Field(..., description="Whether the query was answered")
    completeness: float = Field(..., ge=0.0, le=1.0, description="How complete the answer is")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy/relevance score")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance to query")
    ambiguity_level: float = Field(..., ge=0.0, le=1.0, description="How ambiguous the result is")
    missing_information: List[str] = Field(default_factory=list, description="What's missing")
    data_quality_concerns: List[str] = Field(default_factory=list, description="Quality concerns")
    should_accept: bool = Field(..., description="Whether to accept this result")
    next_step: str = Field(..., description="Recommended next step")
    reasoning: str = Field(..., description="Detailed reasoning for validation decision")


class ValidationResult(BaseModel):
    """Complete validation result"""
    is_sufficient: bool = Field(..., description="Whether results are sufficient to answer query")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    heuristic_issues: List[ValidationIssue] = Field(default_factory=list, description="Issues from heuristic checks")
    semantic_analysis: Optional[SemanticValidation] = Field(None, description="LLM-based analysis")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    next_action: NextAction = Field(..., description="What to do next")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True


class ExtractionResult(BaseModel):
    """Final result from reactive extraction"""
    data: Dict[str, Any] = Field(..., description="Extracted data")
    reasoning_traces: List[ReasoningTrace] = Field(default_factory=list, description="All reasoning traces")
    observations: List[Observation] = Field(default_factory=list, description="All observations")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence per tool")
    total_iterations: int = Field(..., description="Total iterations used")
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Final overall confidence")
    success: bool = Field(..., description="Whether extraction was successful")
    needs_clarification: bool = Field(default=False, description="Whether user clarification is needed")
    clarification_question: Optional[str] = Field(None, description="Question for user if clarification needed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# ORCHESTRATOR MODELS
# ============================================================================

class QueryComplexity(str, Enum):
    """Complexity levels for query analysis"""
    SIMPLE = "simple"        # Single entity, no filters, straightforward
    MEDIUM = "medium"        # Multiple entities OR complex filters
    COMPLEX = "complex"      # Multi-step, aggregations, dependencies


class QueryIntent(str, Enum):
    """Types of query intents"""
    META = "meta"                  # Meta queries (help, capabilities, greetings)
    SEARCH = "search"              # Find entities matching criteria
    COUNT = "count"                # Count matching entities
    ANALYTICS = "analytics"        # Compute aggregations or metrics
    GET_BY_ID = "get_by_id"       # Retrieve specific entity
    LIST = "list"                  # List all entities (no filters)
    RELATIONSHIP = "relationship"  # Find relationships between entities


class ExtractorStrategy(str, Enum):
    """Strategy for data extraction"""
    STATIC = "static"        # Use DataExtractor (predictable, fast)
    REACTIVE = "reactive"    # Use ReActiveDataExtractor (adaptive, thorough)
    HYBRID = "hybrid"        # Start static, fallback to reactive if needed


class ValidationLevel(str, Enum):
    """Level of validation to perform"""
    NONE = "none"            # Skip validation (high confidence queries)
    HEURISTIC = "heuristic"  # Fast rule-based checks only
    SEMANTIC = "semantic"    # Deep LLM-based validation


class QueryAnalysis(BaseModel):
    """Analysis of a user query"""
    complexity: QueryComplexity = Field(..., description="Complexity level of query")
    intent: QueryIntent = Field(..., description="Primary intent of query")
    entities_mentioned: List[str] = Field(default_factory=list, description="Entities mentioned in query")
    filters_detected: List[str] = Field(default_factory=list, description="Filters/conditions detected")
    clarity_score: float = Field(..., ge=0.0, le=1.0, description="How clear/unambiguous the query is")
    requires_optimization: bool = Field(..., description="Whether query needs optimization")
    estimated_steps: int = Field(..., ge=1, description="Estimated number of steps needed")
    reasoning: str = Field(..., description="Explanation of analysis")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ExecutionPlan(BaseModel):
    """Orchestrator's execution plan"""
    # Decision flags
    should_optimize_query: bool = Field(..., description="Whether to run QueryOptimizer")
    extractor_strategy: ExtractorStrategy = Field(..., description="Which extractor to use")
    validation_level: ValidationLevel = Field(..., description="Level of validation")

    # Execution parameters
    max_retries: int = Field(default=1, ge=0, le=3, description="Maximum retry attempts")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence to accept")
    timeout_seconds: Optional[int] = Field(None, description="Execution timeout")

    # Metadata
    reasoning: str = Field(..., description="Explanation of plan decisions")
    estimated_cost: str = Field(default="medium", description="Estimated token/compute cost")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentExecution(BaseModel):
    """Record of an agent execution"""
    agent_name: str = Field(..., description="Name of agent executed")
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(None)
    duration_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    success: bool = Field(..., description="Whether execution succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    result_summary: Optional[str] = Field(None, description="Brief summary of result")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OrchestrationResult(BaseModel):
    """Final result from orchestrator"""
    # Results
    success: bool = Field(..., description="Whether orchestration succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Final response data")

    # Execution tracking
    query_analysis: QueryAnalysis = Field(..., description="Query analysis")
    execution_plan: ExecutionPlan = Field(..., description="Execution plan used")
    agents_executed: List[AgentExecution] = Field(default_factory=list, description="Agents that were executed")

    # Metrics
    total_time_ms: int = Field(..., description="Total execution time")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    retry_count: int = Field(default=0, description="Number of retries performed")

    # Status
    needs_clarification: bool = Field(default=False, description="Whether user clarification needed")
    clarification_question: Optional[str] = Field(None, description="Question if clarification needed")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
