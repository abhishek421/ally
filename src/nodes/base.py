"""Base node class and utilities."""

from abc import ABC, abstractmethod
from typing import Any

from ..graph.state import GraphState
from ..utils.exceptions import NodeExecutionError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseNode(ABC):
    """Base class for all graph nodes."""

    def __init__(self, name: str):
        """Initialize base node."""
        self.name = name
        self.logger = get_logger(f"node.{name}")

    @abstractmethod
    def execute(self, state: GraphState) -> dict[str, Any]:
        """Execute the node logic.

        Args:
            state: Current graph state

        Returns:
            Dictionary of state updates
        """
        pass

    def __call__(self, state: GraphState) -> dict[str, Any]:
        """Make node callable."""
        try:
            self.logger.info("Executing node", node_name=self.name)
            result = self.execute(state)
            self.logger.info("Node execution completed", node_name=self.name)
            return result
        except Exception as e:
            self.logger.error(
                "Node execution failed",
                node_name=self.name,
                error=str(e),
                exc_info=True,
            )
            raise NodeExecutionError(self.name, str(e), e) from e

