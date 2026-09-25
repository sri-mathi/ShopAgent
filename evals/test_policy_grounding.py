import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from app.agent.graph import run_agent
from app.services.policy_rag import retrieve_policy
from judge_model import GroqJudge

GROUNDING_CASES = [
    "Can I return an item after 20 days?",
    "Do you ship internationally?",
    "What's your warranty policy on electronics?",
]

judge = GroqJudge()


@pytest.mark.parametrize("question", GROUNDING_CASES)
def test_policy_faithfulness(question):
    retrieved_chunks = retrieve_policy(question, store_id="store_mock_001")
    retrieval_context = [chunk["content"] for chunk in retrieved_chunks]
    actual_output = run_agent(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )
    metric = FaithfulnessMetric(threshold=0.7, model=judge, include_reason=True)
    assert_test(test_case, [metric])
