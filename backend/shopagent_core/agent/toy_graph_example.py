from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class GreetState(TypedDict):
    name: str
    message: str


def greet(state: GreetState) -> dict:
    return {"message": f"Hello, {state['name']}!"}


def shout(state: GreetState) -> dict:
    return {"message": state["message"].upper()}


def empty_name(state: GreetState) -> dict:
    return {"message": "Error: name is required"}


def route_on_name(state: GreetState) -> str:
    if state["name"] == "":
        return "empty_name"
    return "greet"


graph = StateGraph(GreetState)
graph.add_node("greet", greet)
graph.add_node("shout", shout)
graph.add_node("empty_name", empty_name)

graph.add_conditional_edges(
    START,
    route_on_name,
    {
        "greet": "greet",
        "empty_name": "empty_name",
    },
)

graph.add_edge("greet", "shout")
graph.add_edge("shout", END)
graph.add_edge("empty_name", END)

app = graph.compile()


if __name__ == "__main__":
    print(app.invoke({"name": "Alex", "message": ""}))
    print(app.invoke({"name": "", "message": ""}))
