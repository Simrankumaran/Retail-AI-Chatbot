
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
        # Use interrupt_after_tool=True so the agent stops after calling a tool
        # and returns control to this wrapper instead of potentially re-entering
        # the agent graph (which can cause recursion in langgraph).
        self.agent_node = create_react_agent(
            model=self.llm, tools=self.tools, interrupt_after_tool=True
        )

        self.graph = None

    def agent_fn(self, state: MessagesState):
        # Inject system prompt, then run the ReAct agent node
        messages = state.get("messages", [])
        input_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        result = self.agent_node.invoke({"messages": input_messages})
        # Debug: print full result so developers can inspect roles and tool outputs
        print("agent invoke result:", result)
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
        # Fast path: if user asks directly for an order id, skip the agent graph
        # to avoid recursion and return DB-backed status immediately.
        import re
        from app.utils.order_service import order_by_id

        m = re.search(r"order\s+(\d{3,})", query, flags=re.IGNORECASE)
        if m:
            order_id = m.group(1)
            return order_by_id(order_id)

        result = graph.invoke({"messages": [HumanMessage(content=query)]})
        msgs = result.get("messages", [])
        # Collect tool outputs and assistant replies
        tool_contents = []
        assistant_contents = []
        for m in msgs:
            content = getattr(m, "content", None)
            role = getattr(m, "role", None)
            name = getattr(m, "name", None)
            # Messages coming from tools often have a `name` or `tool_call_id`
            if name or getattr(m, "tool_call_id", None):
                if content:
                    tool_contents.append(content)
            if role == "assistant" and content:
                assistant_contents.append(content)

        # If the assistant returned a final message, prefer it unless it explicitly
        # says it has no info but a tool provided an answer — in that case, return tool output.
        if assistant_contents:
            final = assistant_contents[-1]
            lower = final.lower()
            negative_phrases = ["don't have information", "no information", "don't know", "no details", "not found"]
            if any(p in lower for p in negative_phrases) and tool_contents:
                return tool_contents[-1]
            return final

        # If no assistant reply, but we have tool output, return the most relevant tool output
        if tool_contents:
            return tool_contents[-1]

        # Last resort: return the last message with content
        for m in reversed(msgs):
            content = getattr(m, "content", None)
            if content:
                return content

        return "No answer."
    return run_agent
