from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.tools import TOOLS

load_dotenv()

SYSTEM_PROMPT = (
    "You are ShopAgent, a helpful customer support assistant for an online store. "
    "Answer using only information returned by your tools - never invent product "
    "details, prices, order statuses, or policy terms. If a tool returns an error "
    "or no results, say so honestly instead of guessing. Keep responses concise "
    "and friendly."
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


def run_agent(user_message: str) -> str:
    result = app.invoke(
        {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message)]}
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    print(run_agent("Where is my order ORD1001?"))
    print()
    print(run_agent("Do you have red running shoes under $80?"))
    print()
    print(run_agent("Can I return an item after 20 days?"))
