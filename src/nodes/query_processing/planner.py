"""Planning module and DSPy signatures for query processing."""

from typing import Optional

import dspy

from ...prompts import PLAN_FALLBACK_PROMPT_TEMPLATE, PLAN_GENERATION_INSTRUCTIONS
from ...utils.logger import get_logger

logger = get_logger(__name__)


class GeneratePlan(dspy.Signature):
    """Generate a step-by-step plan to answer the user's request using available tools.

    {instructions}
    """.format(
        instructions=PLAN_GENERATION_INSTRUCTIONS
    )

    context = dspy.InputField(desc="Context including available tools and conversation history")
    question = dspy.InputField(desc="The user's question or request")
    plan = dspy.OutputField(desc="A clear, numbered list of steps to execute")


class Planner(dspy.Module):
    """Planning module that generates execution plans."""

    def __init__(self) -> None:
        super().__init__()
        self.generate_plan = dspy.Predict(GeneratePlan)

    def forward(self, question: str, context: str) -> str:
        """Generate a plan for the given question and context."""
        try:
            response = self.generate_plan(context=context, question=question)
            return response.plan
        except Exception as exc:  # pragma: no cover - fallback path
            logger.warning(
                "Planner failed to generate structured plan: %s. Fallback to simple generation.", exc
            )
            lm = dspy.settings.lm
            prompt = PLAN_FALLBACK_PROMPT_TEMPLATE.format(context=context, question=question)
            return lm(prompt)

