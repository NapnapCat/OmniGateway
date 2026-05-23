from app.agent.state import AgentState

__all__ = ["graph_app", "AgentState"]


def __getattr__(name: str):
    if name == "graph_app":
        from app.agent.graph import graph_app

        return graph_app
    raise AttributeError(name)
