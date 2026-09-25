import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.graph import SYSTEM_PROMPT, app

TOOL_SELECTION_CASES = [
    ("Where is order ORD1001?", "get_order_status"),
    ("What's the status of my order ORD1005?", "get_order_status"),
    ("Do you have red running shoes under $80?", "search_products"),
    ("What electronics do you have in stock?", "search_products"),
    ("Can I return an item after 20 days?", "search_policies"),
    ("Do you ship internationally?", "search_policies"),
]


def get_first_tool_call(user_message: str) -> str | None:
    for step in app.stream(
        {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message)]}
    ):
        for node, update in step.items():
            if node == "agent":
                ai_message = update["messages"][-1]
                if ai_message.tool_calls:
                    return ai_message.tool_calls[0]["name"]
                return None
    return None


@pytest.mark.parametrize("question,expected_tool", TOOL_SELECTION_CASES)
def test_tool_selection(question, expected_tool):
    actual_tool = get_first_tool_call(question)
    assert actual_tool == expected_tool, (
        f"Question {question!r} called tool {actual_tool!r}, expected {expected_tool!r}"
    )
