import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.tools import TOOLS

load_dotenv()

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
    "not render Markdown."
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


def run_agent(user_message: str, session_id: str | None = None) -> str:
    config: dict = {"run_name": "shopagent-chat-response"}
    if _langfuse_handler:
        config["callbacks"] = [_langfuse_handler]
        if session_id:
            config["metadata"] = {"langfuse_session_id": session_id}

    result = app.invoke(
        {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message)]},
        config=config,
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    print(run_agent("Where is my order ORD1001?"))
    print()
    print(run_agent("Do you have red running shoes under $80?"))
    print()
    print(run_agent("Can I return an item after 20 days?"))
