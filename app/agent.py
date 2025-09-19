from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm import load_llm
from app.tools.product import product_tool_list
from app.tools.order import order_tool_list
from app.tools.return_policy import return_policy_tool_list
import json

SYSTEM_PROMPT = (
    "You are a helpful retail assistant for USER 2001. All queries are related to user ID 2001 unless explicitly stated otherwise.\n"
    "\n"
    "CONTEXT: You are assisting USER 2001 with their retail inquiries, orders, and general questions.\n"
    "\n"
    "Use tools exactly as follows:\n"
    "- If the question is about returns, refunds, exchanges, deadlines, eligibility, or policy details, ALWAYS call ReturnPolicyTool first.\n"
    "- If the user asks about product details, availability, or price, use ProductSearchTool.\n"
    "- If the user asks about order status and provides an order ID, use OrderTrackingTool.\n"
    "- If the user asks about order status without an order ID but mentions a product name, use OrderTrackingByProductTool.\n"
    "- If the user asks about 'my orders', 'my recent orders', or similar personal queries, use MyOrdersTool.\n"
    "- If the user asks about all recent orders in the system, use AllOrdersTool.\n"
    "- If the user asks about orders by status (pending, shipped, delivered, cancelled), use OrdersByStatusTool.\n"
    "- If the user asks about orders by a specific user ID, use OrdersByUserTool.\n"
    "- If the user wants to cancel an order and provides an order ID, first use OrderCancellationCheckTool to check if cancellation is possible, then use OrderCancellationTool to cancel it.\n"
    "- If the user asks which orders can be cancelled or wants to see cancellable orders, use CancellableOrdersTool (defaults to user 2001).\n"
    "\n"
    "TOOLS RETURN STRUCTURED DATA:\n"
    "- Each tool returns a dictionary with a boolean key 'found' or 'success' or 'can_cancel'.\n"
    "- If 'found' is True, additional keys like 'order_id', 'orders', 'product_name', 'user_id', or 'status' contain the relevant information.\n"
    "- If 'found' is False, keys like 'error', 'order_id', 'product_name', or 'user_id' indicate what was searched for.\n"
    "- For cancellation: 'can_cancel' indicates if cancellation is possible, 'success' indicates if cancellation was completed.\n"
    "\n"
    "INSTRUCTIONS FOR RESPONDING:\n"
    "- When 'found' is True, extract and present the key information clearly:\n"
    "  * For orders: mention order ID, product name, status, date, and return eligibility if available\n"
    "  * For products: mention name, price, and category\n"
    "  * For policies: provide the relevant policy information\n"
    "  * For cancellations: explain the cancellation status and any restrictions\n"
    "- If 'found' is False, inform the user politely that no matching results were found.\n"
    "- For cancellation requests: Always check cancellation eligibility first, then proceed with cancellation if allowed.\n"
    "- Always base your response on the tool output; do not guess or make up information.\n"
    "- Respond in a conversational, helpful tone.\n"
    "- When referring to orders, you can use 'your orders' since you're assisting user 2001.\n"
    "- Assume queries about 'my orders', 'my cancellable orders', etc. refer to user 2001."
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

    def extract_final_ai_message(msgs):
        """Return the last non-empty AI/assistant message content."""
        # Reverse iterate to get the LAST AI message (final response)
        for msg in reversed(msgs):
            # Check if it's an AI message using type name
            msg_type_name = type(msg).__name__
            
            if msg_type_name == 'AIMessage':
                content = getattr(msg, "content", "")
                if content and content.strip():
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

            # Extract the final AI message first
            last_assistant_msg = extract_final_ai_message(msgs)
            
            # Only check for "not found" if we don't have a proper AI response
            if not last_assistant_msg or len(last_assistant_msg.strip()) < 10:
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
                        return "You didn't order this item, so I cannot provide its status."

            # Return the AI assistant's response if we have one
            if last_assistant_msg:
                return last_assistant_msg

            return "No answer."

        except Exception as e:
            import traceback
            print("Agent crashed:\n", traceback.format_exc())
            return f"Agent error: {e}"

    return run_agent
