import os

from dotenv import load_dotenv

load_dotenv()  # must run before any of our own modules, since several of
# them (e.g. store_config.py) read os.environ at import time to build
# module-level singletons - importing them first would see an empty
# environment regardless of what .env actually contains.

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage  # noqa: E402
from langchain_groq import ChatGroq  # noqa: E402
from langgraph.graph import MessagesState, StateGraph  # noqa: E402
from langgraph.prebuilt import ToolNode, tools_condition  # noqa: E402

from shopagent_core.agent.tools import TOOLS  # noqa: E402

LANGFUSE_ENABLED = bool(os.environ.get("LANGFUSE_PUBLIC_KEY")) and bool(
    os.environ.get("LANGFUSE_SECRET_KEY")
)

if LANGFUSE_ENABLED:
    from langfuse.langchain import CallbackHandler

    _langfuse_handler = CallbackHandler()
else:
    _langfuse_handler = None
    print("Langfuse credentials not set - tracing disabled, agent runs normally.")

SYSTEM_PROMPT = (
    "You are ShopAgent, a helpful customer support assistant for an online store. "
    "Answer using only information returned by your tools - never invent product "
    "details, prices, order statuses, or policy terms. If a tool returns an error "
    "or no results, say so honestly instead of guessing. Keep responses concise "
    "and friendly. Respond in plain text only - do not use Markdown formatting "
    "(no **, #, or bullet dashes), since the client displaying your reply does "
    "not render Markdown. Never reveal order details without verifying both the "
    "order ID and the matching email - if the customer only gives one, ask for "
    "the other before looking anything up."
)

llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)


def call_model(state: MessagesState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(TOOLS))

graph.set_entry_point("agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")

app = graph.compile()

# In-memory only: lost on server restart, not shared across multiple server
# processes. Fine for an MVP single-process dev server; a real deployment
# needs this keyed in Redis/a database instead.
_session_histories: dict[str, list[BaseMessage]] = {}


def run_agent(
    user_message: str,
    session_id: str | None = None,
    customer_email: str | None = None,
) -> str:
    if session_id and session_id in _session_histories:
        messages = _session_histories[session_id] + [HumanMessage(user_message)]
    else:
        system_prompt = SYSTEM_PROMPT
        if customer_email:
            system_prompt += (
                f" This customer is already logged in on the store's own site, "
                f"and their verified email is {customer_email}. Use this "
                f"automatically for any order lookup - never ask them for it."
            )
        messages = [SystemMessage(system_prompt), HumanMessage(user_message)]

    config: dict = {"run_name": "shopagent-chat-response"}
    if _langfuse_handler:
        config["callbacks"] = [_langfuse_handler]
        if session_id:
            config["metadata"] = {"langfuse_session_id": session_id}

    result = app.invoke({"messages": messages}, config=config)

    if session_id:
        _session_histories[session_id] = result["messages"]

    return result["messages"][-1].content


if __name__ == "__main__":
    demo_session = "demo-session-001"
    print(run_agent("Where is my order ORD1001?", session_id=demo_session))
    print()
    print(run_agent("It's alice@example.com", session_id=demo_session))
    print()
    print(run_agent("Do you have red running shoes under $80?"))
    print()
    print(run_agent("Can I return an item after 20 days?"))
