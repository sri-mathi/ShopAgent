import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agent.graph import SYSTEM_PROMPT, app
from judge_model import GroqJudge

DB_GROUNDING_CASES = [
    "Where is order ORD1005?",
    "What electronics do you have in stock?",
]

judge = GroqJudge()


def run_and_capture_tool_output(user_message: str) -> tuple[str, str]:
    tool_output = None
    final_answer = None
    for step in app.stream(
        {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message)]}
    ):
        for node, update in step.items():
            for msg in update["messages"]:
                if isinstance(msg, ToolMessage):
                    tool_output = msg.content
                elif node == "agent" and not getattr(msg, "tool_calls", None):
                    final_answer = msg.content
    return tool_output, final_answer


@pytest.mark.parametrize("question", DB_GROUNDING_CASES)
def test_db_tool_output_faithfulness(question):
    tool_output, actual_output = run_and_capture_tool_output(question)
    assert tool_output is not None, f"No tool was called for: {question!r}"

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=[tool_output],
    )
    metric = FaithfulnessMetric(threshold=0.7, model=judge, include_reason=True)
    assert_test(test_case, [metric])
