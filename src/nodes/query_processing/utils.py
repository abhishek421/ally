"""Shared utilities for the query processing node."""

import dspy

from ...config import get_settings
from ...utils.dspy_adapter import get_dspy_lm

settings = get_settings()
_dspy_lm = None


def get_or_create_dspy_lm() -> dspy.LM:
    """Get or create the global DSPy language model instance."""
    global _dspy_lm  # noqa: PLW0603
    if _dspy_lm is None:
        _dspy_lm = get_dspy_lm(model_name=settings.query_processing_model)
        dspy.configure(lm=_dspy_lm)
    return _dspy_lm

