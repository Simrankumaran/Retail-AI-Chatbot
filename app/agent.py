
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm import load_llm
from app.tools.product import product_tool_list
from app.tools.order import order_tool_list
from app.tools.return_policy import return_policy_tool_list

SYSTEM_PROMPT = (
    "You are a helpful retail assistant. Use tools exactly as follows:\n"
    "- If the question is about returns, refunds, exchanges, deadlines, eligibility, or policy details, ALWAYS call ReturnPolicyTool first.\n"
    "- If the user asks about product details, availability, or price, use ProductSearchTool.\n"
    "- If the user asks about order status and provides an order ID, use OrderTrackingTool.\n"
    "- If the user asks about order status without an order ID but mentions a product name, use OrderTrackingByProductTool.\n"
    "- If tools provide no relevant information, say you don't know rather than guessing.\n"
    "Respond concisely and ground answers in tool results."
)

class GraphBuilder:
    def __init__(self) -> None:
        self.llm = load_llm()
        # Combine all exported tools, keeping single-tool names for backward compatibility
        self.tools = [
            *product_tool_list,
            *order_tool_list,
            *return_policy_tool_list,
        ]
        # Use ReAct-style agent that works without structured tool-calling support
        self.agent_node = create_react_agent(model=self.llm, tools=self.tools, interrupt_after_tool=True)
        self.graph = None
    def agent_fn(self, state: MessagesState):
        # Inject system prompt, then run the ReAct agent node
        messages = state.get("messages", [])
        input_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        result = self.agent_node.invoke({"messages": input_messages})
        print(result.get("messages", []))
        return {"messages": result.get("messages", [])}
    
    def build(self):
        g = StateGraph(MessagesState)
        g.add_node("agent", self.agent_fn)
        g.add_edge(START, "agent")
        g.add_edge("agent", END)
        self.graph = g.compile()
        return self.graph

def get_agent():
    builder = GraphBuilder()
    graph = builder.build()
    def run_agent(query: str) -> str:
        result = graph.invoke({"messages": [HumanMessage(content=query)]})
        msgs = result.get("messages", [])
        return getattr(msgs[-1], "content", "No answer.") if msgs else "No answer."
    return run_agent
