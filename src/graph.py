"""
LangGraph pipeline definition for the CRM AI Copilot.

This module constructs and exports the complete agent graph that processes
user queries through a multi-stage pipeline:

Pipeline Flow:
    User Input
        ↓
    Planner Node
        ↓ (creates plan)
    Validator Node
        ↓ (validates/modifies plan)
    [Conditional Routing]
        ↓ (if CONFIRMATION_REQUIRED or NONE → skip to final_response)
        ↓ (otherwise → continue to executor)
    Executor Node
        ↓ (executes tools)
    Aggregator Node
        ↓ (normalizes results)
    Final Response Node
        ↓
    Output to Frontend

Node Responsibilities:

1. Planner Node
   - Analyzes user input and conversation context
   - Calls LLM to generate execution plan
   - Returns structured plan with tasks and decision type

2. Validator Node
   - Detects user confirmations of pending actions
   - Converts write operations into pending confirmations
   - Validates task arguments and constraints
   - Routes to executor or skips to final_response

3. Executor Node
   - Executes planned tasks using tool registry
   - Handles SEQUENTIAL vs PARALLEL execution
   - Captures results and errors
   - Never raises exceptions

4. Aggregator Node
   - Normalizes tool results into semantic categories
   - Creates tool activity logs
   - Combines metadata from plan and execution
   - Prepares data for final_response

5. Final Response Node
   - Converts aggregated data to UI-friendly format
   - Builds structured message blocks
   - Returns final response for frontend rendering

Tool Registry:

All available tools are collected into a single registry dictionary:
    {
        "search_people": async_callable,
        "get_person": async_callable,
        "create_company": async_callable,
        ...
    }

This registry is injected into the executor and planner nodes so they can
look up and call tools by name.

Conditional Routing:

The graph uses conditional edges to route based on node outputs:

After Validator:
- CONFIRMATION_REQUIRED → final_response (skip execution, wait for user)
- NONE → final_response (no tasks to execute)
- Otherwise → executor (proceed with execution)

After Executor:
- NONE → final_response (no results to aggregate)
- Otherwise → aggregator (normalize and merge results)

Memory & Checkpointing:

The graph uses LangGraph's MemorySaver for conversation persistence:
- Each conversation has a unique thread_id
- State is checkpointed after each node
- Allows resuming conversations and implementing undo/redo
- Enables streaming with state recovery

Integration with Server:

The compiled graph is exported as `graph_app` and used by server/http_server.py:

1. Server receives user message
2. Loads state from session store (Redis)
3. Invokes graph with user input
4. Streams events to frontend via SSE
5. Saves updated state to session store

Future Enhancements:

TODO: Add human-in-the-loop node for complex decisions
TODO: Add memory retrieval node for RAG-style context
TODO: Add parallel branches for independent query processing
TODO: Add retry logic node for transient failures
TODO: Add caching layer for frequently used tool results
TODO: Add metrics/observability instrumentation
TODO: Add A/B testing support for different planning strategies
"""

from typing import Dict, Any, Callable, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Import state
from src.memory.state import AgentState

# Import all nodes
from src.nodes.planner import planner_node
from src.nodes.validator import validator_node
from src.nodes.executor import executor_node
from src.nodes.aggregator import aggregator_node
from src.nodes.final_response import final_response_node

# Import all tool modules
from src.tools import workspace_tools
from src.tools import company_tools
from src.tools import people_tools
from src.tools import group_tools
from src.tools import interactions_tools

from src.config.logger import logger


# ========================================
# Tool Registry Builder
# ========================================


def build_tool_registry() -> Dict[str, Callable]:
    """
    Build a registry of all available tools for the agent.
    
    Collects tools from all tool modules and returns them in a single
    dictionary mapping tool names to their async callable functions.
    
    This registry is injected into the executor and planner nodes so they
    can look up and invoke tools by name.
    
    Returns:
        Dictionary mapping tool names to async callable functions:
        {
            "search_people": async_function,
            "get_person": async_function,
            ...
        }
    
    Example:
        registry = build_tool_registry()
        tool_fn = registry["search_people"]
        result = await tool_fn(workspace_id="ws-123", user_id="u-456")
    """
    registry = {}
    
    try:
        # ========================================
        # Workspace Tools
        # ========================================
        
        for tool in workspace_tools.WORKSPACE_TOOLS:
            registry[tool.__name__] = tool
        
        logger.debug(f"Registered {len(workspace_tools.WORKSPACE_TOOLS)} workspace tools")
        
        # ========================================
        # Company Tools
        # ========================================
        
        for tool in company_tools.COMPANY_TOOLS:
            registry[tool.__name__] = tool
        
        logger.debug(f"Registered {len(company_tools.COMPANY_TOOLS)} company tools")
        
        # ========================================
        # People Tools
        # ========================================
        
        for tool in people_tools.PEOPLE_TOOLS:
            registry[tool.__name__] = tool
        
        logger.debug(f"Registered {len(people_tools.PEOPLE_TOOLS)} people tools")
        
        # ========================================
        # Group Tools
        # ========================================
        
        for tool in group_tools.GROUP_TOOLS:
            registry[tool.__name__] = tool
        
        logger.debug(f"Registered {len(group_tools.GROUP_TOOLS)} group tools")
        
        # ========================================
        # Interaction Tools
        # ========================================
        
        for tool in interactions_tools.INTERACTION_TOOLS:
            registry[tool.__name__] = tool
        
        logger.debug(f"Registered {len(interactions_tools.INTERACTION_TOOLS)} interaction tools")
        
        # TODO: Add future tool modules here as they are created
        # TODO: Add deal_tools when implemented
        # TODO: Add analytics_tools when implemented
        # TODO: Add integration_tools when implemented
        # TODO: Add admin_tools when implemented
        
        logger.info(f"Tool registry built with {len(registry)} total tools")
        
        return registry
    
    except Exception as e:
        logger.error(f"Error building tool registry: {e}", exc_info=True)
        # Return empty registry on error - graph can still function for non-tool operations
        return {}


# ========================================
# Router Functions
# ========================================


def validator_router(state: AgentState) -> Literal["executor", "final_response"]:
    """
    Route after validator based on plan decision type.
    
    Determines the next node based on the validated plan's decision type:
    - CONFIRMATION_REQUIRED: Skip to final_response (wait for user confirmation)
    - NONE: Skip to final_response (no tasks to execute)
    - Otherwise: Continue to executor (execute planned tasks)
    
    Args:
        state: Current agent state (must contain validated plan in a field)
    
    Returns:
        Next node name: "executor" or "final_response"
    
    Note:
        This function examines the plan that was stored in state by the validator.
        In the actual graph, the validator's output (the plan) will be passed through.
    """
    # In practice, the graph framework will pass the validator's output
    # For now, we'll check if there's a pending_action or look at reasoning
    
    # Check if there's a pending action (confirmation required)
    if state.pending_action is not None:
        logger.info("Router: CONFIRMATION_REQUIRED - routing to final_response")
        return "final_response"
    
    # Check if it's a NONE decision
    # The validator might have set decision_type to NONE if validation failed
    # Or if the planner couldn't generate a plan
    if state.plan and state.plan.get("decision_type") == "NONE":
        logger.info("Router: NONE decision - routing to final_response")
        return "final_response"

    # Check if there are any tool calls logged (indicates execution happened)
    # If no tool calls and no pending action, likely a NONE decision
    # BUT this check is flawed for the validator router because execution hasn't happened yet!
    # We should rely on the plan's decision_type and tasks list instead.
    
    if state.plan and state.plan.get("tasks") and len(state.plan.get("tasks")) > 0:
        logger.info(f"Router: Proceeding to executor with {len(state.plan.get('tasks'))} tasks")
        return "executor"
    
    # Fallback: if no tasks and no pending action, it's likely a NONE or empty plan
    logger.info("Router: No tasks or pending action - routing to final_response")
    return "final_response"


def executor_router(state: AgentState) -> Literal["aggregator", "final_response"]:
    """
    Route after executor based on execution results.
    
    Determines the next node based on whether any tools were executed:
    - No execution (NONE mode): Skip to final_response
    - Execution occurred: Continue to aggregator for result normalization
    
    Args:
        state: Current agent state with execution results
    
    Returns:
        Next node name: "aggregator" or "final_response"
    
    Note:
        In practice, the graph framework will pass the executor's output.
        We check if any tool results were returned to determine routing.
    """
    # Check if any tool executions occurred by examining execution_results
    if not state.execution_results:
        logger.info("Router: No execution_results in state - routing to final_response")
        return "final_response"
    
    results = state.execution_results.get("results", [])
    
    if not results or len(results) == 0:
        logger.info("Router: No tool results - routing to final_response")
        return "final_response"
    
    # Check if any results were successful
    success_count = sum(1 for r in results if r.get("status") == "success")
    
    if success_count == 0:
        logger.info(f"Router: All {len(results)} tool(s) failed - routing to final_response")
        return "final_response"
    
    # Tool executions occurred with at least one success - proceed to aggregator
    logger.info(f"Router: Found {success_count} successful tool result(s) - routing to aggregator")
    return "aggregator"


# ========================================
# Graph Builder
# ========================================


def build_graph() -> Any:
    """
    Build and compile the complete LangGraph pipeline.
    
    This function constructs the agent graph by:
    1. Building the tool registry
    2. Injecting tools into nodes that need them
    3. Creating the StateGraph with AgentState
    4. Adding all nodes (planner, validator, executor, aggregator, final_response)
    5. Defining edges and conditional routing
    6. Setting entry and finish points
    7. Compiling with memory checkpointing
    
    The resulting graph is a compiled state machine that can process
    user inputs through the complete pipeline.
    
    Returns:
        Compiled LangGraph application ready to invoke
    
    Example Usage:
        graph = build_graph()
        
        # Invoke graph with user input
        result = graph.invoke(
            {
                "conversation_id": "conv-123",
                "user_id": "user-456",
                "workspace_id": "ws-789",
                "messages": []
            },
            config={"configurable": {"thread_id": "conv-123"}}
        )
    """
    logger.info("Building LangGraph pipeline...")
    
    try:
        # ========================================
        # 1. Build Tool Registry
        # ========================================
        
        tools = build_tool_registry()
        
        # Inject tools into nodes that need them
        # TODO: Implement proper dependency injection
        # For now, tools are accessed via global variables in each node module
        # In production, we'd pass tools as function arguments or via context
        
        # Import node modules to set their TOOL_REGISTRY
        from src.nodes import planner, executor
        planner.TOOL_REGISTRY = tools
        executor.TOOL_REGISTRY = tools
        
        logger.info("Tool registry injected into nodes")
        
        # ========================================
        # 2. Create StateGraph
        # ========================================
        
        graph = StateGraph(AgentState)
        
        logger.debug("Created StateGraph with AgentState")
        
        # ========================================
        # 3. Add Nodes
        # ========================================
        
        logger.debug(f"Adding planner node: {type(planner_node)}")
        graph.add_node("planner", planner_node)
        
        logger.debug(f"Adding validator node: {type(validator_node)}")
        graph.add_node("validator", validator_node)
        
        logger.debug(f"Adding executor node: {type(executor_node)}")
        graph.add_node("executor", executor_node)
        
        logger.debug(f"Adding aggregator node: {type(aggregator_node)}")
        graph.add_node("aggregator", aggregator_node)
        
        logger.debug(f"Adding final_response node: {type(final_response_node)}")
        graph.add_node("format_response", final_response_node)
        
        logger.debug("Added all 5 nodes to graph")
        
        # ========================================
        # 4. Set Entry Point
        # ========================================
        
        graph.set_entry_point("planner")
        
        logger.debug("Set entry point to planner")
        
        # ========================================
        # 5. Add Edges
        # ========================================
        
        # Planner always flows to validator
        graph.add_edge("planner", "validator")
        
        # Validator routes conditionally
        graph.add_conditional_edges(
            "validator",
            validator_router,
            {
                "executor": "executor",
                "final_response": "format_response"
            }
        )
        
        # Executor routes conditionally
        graph.add_conditional_edges(
            "executor",
            executor_router,
            {
                "aggregator": "aggregator",
                "final_response": "format_response"
            }
        )
        
        # Aggregator always flows to format_response
        graph.add_edge("aggregator", "format_response")
        
        # Format response is the end
        graph.set_finish_point("format_response")
        
        logger.debug("Added all edges and conditional routing")
        
        logger.debug("Set finish point to format_response")
        
        # ========================================
        # 7. Compile Graph with Memory
        # ========================================
        
        # Create memory saver for conversation persistence
        memory = MemorySaver()
        
        # Compile the graph
        compiled_graph = graph.compile(checkpointer=memory)
        
        logger.info("Graph compiled successfully with memory checkpointing")
        
        return compiled_graph
    
    except Exception as e:
        logger.error(f"Error building graph: {e}", exc_info=True)
        raise RuntimeError(f"Failed to build LangGraph pipeline: {e}")


# ========================================
# Export Compiled Graph
# ========================================

# Build and export the graph application
# This is imported by main.py and server modules
try:
    graph_app = build_graph()
    logger.info("Graph application ready")
except Exception as e:
    logger.critical(f"Failed to initialize graph application: {e}")
    # In production, you might want to use a fallback or raise
    raise


# ========================================
# Development Utilities
# ========================================


def get_graph_visualization() -> str:
    """
    Generate a text visualization of the graph structure.
    
    Useful for debugging and documentation.
    
    Returns:
        ASCII representation of the graph
    """
    return """
    LangGraph Pipeline Visualization:
    
    [START]
       ↓
    [Planner]
       ↓
    [Validator]
       ↓
      / \\
     /   \\
    ↓     ↓
 [Executor]  [Final Response] ←─┐
    ↓                           │
    |                           │
   / \\                          │
  /   \\                         │
 ↓     ↓                        │
[Aggregator]  [Final Response]──┘
 ↓
[Final Response]
 ↓
[END]

Routing Logic:
- Validator → Final Response: If CONFIRMATION_REQUIRED or NONE
- Validator → Executor: Otherwise
- Executor → Final Response: If no executions (NONE mode)
- Executor → Aggregator: If executions occurred
- Aggregator → Final Response: Always
"""


def list_all_tools() -> list[str]:
    """
    List all registered tool names.
    
    Useful for debugging and documentation.
    
    Returns:
        List of tool names
    """
    try:
        registry = build_tool_registry()
        return sorted(registry.keys())
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return []


if __name__ == "__main__":
    # Development utilities
    print(get_graph_visualization())
    print("\nRegistered Tools:")
    for tool_name in list_all_tools():
        print(f"  - {tool_name}")

