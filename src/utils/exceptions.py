"""Custom exceptions for the application."""


class NodeExecutionError(Exception):
    """Raised when a node execution fails."""

    def __init__(self, node_name: str, message: str, original_error: Exception | None = None):
        self.node_name = node_name
        self.original_error = original_error
        super().__init__(f"Node '{node_name}' failed: {message}")


class GraphExecutionError(Exception):
    """Raised when graph execution fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(f"Graph execution failed: {message}")

