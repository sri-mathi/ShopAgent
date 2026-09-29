import uuid

from shopagent_core.agent.graph import run_agent


def test_host_supplied_email_skips_clarifying_question():
    session_id = f"identity-bypass-{uuid.uuid4()}"
    reply = run_agent(
        "Where is order ORD1002?",
        session_id=session_id,
        customer_email="bob@example.com",
    )
    assert "email" not in reply.lower()
    assert "processing" in reply.lower() or "ship" in reply.lower()


def test_host_supplied_email_still_enforces_ownership():
    session_id = f"identity-bypass-{uuid.uuid4()}"
    reply = run_agent(
        "Where is order ORD1001?",
        session_id=session_id,
        customer_email="bob@example.com",
    )
    assert "shipped" not in reply.lower()
    assert "tracking" not in reply.lower()
