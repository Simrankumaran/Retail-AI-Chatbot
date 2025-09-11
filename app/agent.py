from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm import load_llm
from app.tools.product import product_tool_list
from app.tools.order import order_tool_list
from app.tools.return_policy import return_policy_tool_list
import json
from langchain_core.messages import HumanMessage

SYSTEM_PROMPT = (
    "You are a helpful retail assistant. Use tools exactly as follows:\n"
    "- If the question is about returns, refunds, exchanges, deadlines, eligibility, or policy details, ALWAYS call ReturnPolicyTool first.\n"
    "- If the user asks about product details, availability, or price, use ProductSearchTool.\n"
    "- If the user asks about order status and provides an order ID, use OrderTrackingTool.\n"
    "- If the user asks about order status without an order ID but mentions a product name, use OrderTrackingByProductTool.\n"
    "- If the user asks about all recent orders, use AllOrdersTool.\n"
    "- If the user asks about orders by status (pending, shipped, delivered, cancelled), use OrdersByStatusTool.\n"
    "- If the user asks about orders by a specific user ID, use OrdersByUserTool.\n"
    "\n"
    "TOOLS RETURN STRUCTURED DATA:\n"
    "- Each tool returns a dictionary with a boolean key 'found'.\n"
    "- If 'found' is True, additional keys like 'order_id', 'orders', 'product_name', 'user_id', or 'status' contain the relevant information.\n"
    "- If 'found' is False, keys like 'error', 'order_id', 'product_name', or 'user_id' indicate what was searched for.\n"
    "\n"
    "INSTRUCTIONS FOR RESPONDING:\n"
    "- If 'found' is True, summarize the details in a clear, natural sentence for the user.\n"
    "- If 'found' is False, inform the user politely that no matching order was found.\n"
    "  Example: 'You didn't order this item, so I cannot show its status.'\n"
    "- Always base your response on the tool output; do not guess.\n"
    "- Respond concisely and naturally."
)


class GraphBuilder:
    def __init__(self) -> None:
        self.llm = load_llm()
        self.tools = [
            *product_tool_list,
            *order_tool_list,
            *return_policy_tool_list,
        ]
        self.agent_node = create_react_agent(
            model=self.llm,
            tools=self.tools,
            interrupt_after_tool=False,  # allow multi-step reasoning
        )
        self.graph = None

    def agent_fn(self, state: MessagesState):
        messages = state.get("messages", [])
        input_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        result = self.agent_node.invoke({"messages": input_messages})
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

    def extract_first_ai_message(msgs):
        """Return the first non-empty AI/assistant message."""
        for msg in msgs:
            content = getattr(msg, "content", "")
            if content.strip():
                return content
        return None

    def check_not_found(tool_output):
        """
        Recursively check tool output dictionaries/lists for any 'found: False'.
        Handles nested structures like orders inside product search results.
        """
        if isinstance(tool_output, dict):
            if not tool_output.get("found", True):
                return True
            for val in tool_output.values():
                if isinstance(val, list):
                    for item in val:
                        if check_not_found(item):
                            return True
        elif isinstance(tool_output, list):
            for item in tool_output:
                if check_not_found(item):
                    return True
        return False

    def run_agent(query: str) -> str:
        try:
            result = graph.invoke({"messages": [HumanMessage(content=query)]})
            print("Agent raw result:", result)  # Debugging

            msgs = result.get("messages", [])
            if not msgs:
                return "No answer."

            tool_outputs = []

            for msg in msgs:
                # ToolMessage parsing
                name = getattr(msg, "name", None)
                content = getattr(msg, "content", "")
                if name:
                    try:
                        parsed = json.loads(content)
                        tool_outputs.append(parsed)
                    except Exception:
                        tool_outputs.append({"found": False, "raw": content})

                # AIMessage tool_calls (sometimes results are here)
                tool_calls = getattr(msg, "tool_calls", [])
                for call in tool_calls:
                    tool_msg_content = call.get("result", "{}")
                    try:
                        parsed_call = json.loads(tool_msg_content)
                        tool_outputs.append(parsed_call)
                    except Exception:
                        tool_outputs.append({"found": False, "raw": tool_msg_content})

            # Check all tool outputs for any 'found: False' recursively
            for tool_output in tool_outputs:
                if check_not_found(tool_output):
                    return "You didn’t order this item, so I cannot provide its status."

            # Fallback to last AI/assistant message
            last_assistant_msg = extract_first_ai_message(msgs)
            if last_assistant_msg:
                return last_assistant_msg

            return "No answer."

        except Exception as e:
            import traceback
            print("Agent crashed:\n", traceback.format_exc())
            return f"Agent error: {e}"

    return run_agent

    builder = GraphBuilder()
    graph = builder.build()
    
    def extract_first_ai_message(msgs):
        for msg in msgs:
            content = getattr(msg, "content", "")
            if content.strip():
                return content
        return None


    def run_agent(query: str) -> str:
        try:
            result = graph.invoke({"messages": [HumanMessage(content=query)]})
            print("Agent raw result:", result)  # Debugging

            msgs = result.get("messages", [])
            if not msgs:
                return "No answer."

            last_assistant_msg = None
            tool_outputs = []

            for msg in msgs:
                # ToolMessage
                name = getattr(msg, "name", None)
                content = getattr(msg, "content", "")
                if name:
                    try:
                        parsed = json.loads(content)
                        tool_outputs.append(parsed)
                    except Exception:
                        tool_outputs.append({"found": False, "raw": content})

                # AIMessage
                role = getattr(msg, "role", None)
                if role == "assistant" and content.strip():
                    last_assistant_msg = content

                # AIMessage with tool_calls
                tool_calls = getattr(msg, "tool_calls", [])
                for call in tool_calls:
                    tool_msg_content = call.get("result", "{}")
                    try:
                        parsed_call = json.loads(tool_msg_content)
                        tool_outputs.append(parsed_call)
                    except Exception:
                        tool_outputs.append({"found": False, "raw": tool_msg_content})

            # Check tool outputs for "not found"
            for tool_output in tool_outputs:
                if isinstance(tool_output, dict) and not tool_output.get("found", True):
                    return "You didn’t order this item, so I cannot provide its status."

            # Return last assistant message if exists
            last_assistant_msg = extract_first_ai_message(msgs)
            if last_assistant_msg:
                return last_assistant_msg

        except Exception as e:
            import traceback
            print("Agent crashed:\n", traceback.format_exc())
            return f"Agent error: {e}"

    return run_agent