"""Agent with MongoDB persistence for chat storage."""
from typing import Optional, List
import logging
import time
import uuid

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.llm import load_llm
from app.tools.product import product_tool_list
from app.tools.order import order_tool_list
from app.tools.return_policy import return_policy_tool_list
from app.models import AgentRequest, AgentResponse
from app.utils.session_mongo import (
    init_mongo_collections,
    create_session,
    get_session,
    add_message,
    get_session_messages
)

logger = logging.getLogger(__name__)


def get_system_prompt(user_id: str) -> str:
    """Generate system prompt for a specific user."""
    return f"""You are a helpful retail assistant for USER {user_id}. All queries are related to user ID {user_id} unless explicitly stated otherwise.

CONTEXT: You are assisting USER {user_id} with their retail inquiries, orders, and general questions.

Use tools exactly as follows:
- If the question is about returns, refunds, exchanges, deadlines, eligibility, or policy details, ALWAYS call ReturnPolicyTool first.
- If the user asks about product details, availability, or price, use ProductSearchTool.
- If the user asks about order status and provides an order ID, use OrderTrackingTool.
- If the user asks about order status without an order ID but mentions a product name, use OrderTrackingByProductTool.
- If the user asks about 'my orders', 'my recent orders', or similar personal queries, use MyOrdersTool.
- If the user asks about all recent orders in the system, use AllOrdersTool.
- If the user asks about orders by status (pending, shipped, delivered, cancelled), use OrdersByStatusTool.
- If the user asks about orders by a specific user ID, use OrdersByUserTool.
- If the user wants to cancel an order and provides an order ID, first use OrderCancellationCheckTool to check if cancellation is possible, then use OrderCancellationTool to cancel it.
- If the user asks which orders can be cancelled or wants to see cancellable orders, use CancellableOrdersTool (defaults to user {user_id}).

TOOLS RETURN STRUCTURED DATA:
- Each tool returns a dictionary with a boolean key 'found' or 'success' or 'can_cancel'.
- If 'found' is True, additional keys like 'order_id', 'orders', 'product_name', 'user_id', or 'status' contain the relevant information.
- If 'found' is False, keys like 'error', 'order_id', 'product_name', or 'user_id' indicate what was searched for.
- For cancellation: 'can_cancel' indicates if cancellation is possible, 'success' indicates if cancellation was completed.

INSTRUCTIONS FOR RESPONDING:
- When 'found' is True, extract and present the key information clearly:
  * For orders: mention order ID, product name, status, date, and return eligibility if available
  * For products: mention name, price, and category
  * For policies: provide the relevant policy information
  * For cancellations: explain the cancellation status and any restrictions
- If 'found' is False, inform the user politely that no matching results were found.
- For cancellation requests: Always check cancellation eligibility first, then proceed with cancellation if allowed.
- Always base your response on the tool output; do not guess or make up information.
- Respond in a conversational, helpful tone.
- When referring to orders, you can use 'your orders' since you're assisting user {user_id}.
- Assume queries about 'my orders', 'my cancellable orders', etc. refer to user {user_id}."""


class RetailAgentMongo:
    """Retail assistant agent with MongoDB persistence."""
    
    def __init__(self):
        """Initialize the agent."""
        self.llm = load_llm()
        self.tools = [
            *product_tool_list,
            *order_tool_list,
            *return_policy_tool_list,
        ]
        # Initialize MongoDB collections
        try:
            init_mongo_collections()
            logger.info("RetailAgentMongo initialized with MongoDB storage")
        except Exception as e:
            logger.error("Failed to initialize MongoDB: %s", str(e))
            raise
    
    def _create_react_agent(self, user_id: str):
        """Create a react agent for a specific user."""
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            interrupt_after_tool=False,
        )
    
    def _build_graph(self, user_id: str) -> StateGraph:
        """Build the agent graph for a specific user."""
        agent_node = self._create_react_agent(user_id)
        system_prompt = get_system_prompt(user_id)
        
        def agent_fn(state: MessagesState):
            messages = state.get("messages", [])
            input_messages = [SystemMessage(content=system_prompt)] + messages
            result = agent_node.invoke({"messages": input_messages})
            return {"messages": result.get("messages", [])}
        
        graph = StateGraph(MessagesState)
        graph.add_node("agent", agent_fn)
        graph.add_edge(START, "agent")
        graph.add_edge("agent", END)
        return graph.compile()
    
    def _extract_final_ai_message(self, messages: List) -> Optional[str]:
        """Extract the last AI message content."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) or type(msg).__name__ == 'AIMessage':
                content = getattr(msg, "content", "")
                if content and content.strip():
                    return content
        return None
    
    def _extract_tools_used(self, messages: List) -> List[str]:
        """Extract list of tools that were called."""
        tools = []
        for msg in messages:
            tool_name = getattr(msg, "name", None)
            if tool_name and tool_name not in tools:
                tools.append(tool_name)
        return tools
    
    def run(self, request: AgentRequest) -> AgentResponse:
        """
        Process a user query with MongoDB persistence.
        
        Args:
            request: AgentRequest with query, user_id, and optional session_id
            
        Returns:
            AgentResponse with answer and metadata
        """
        start_time = time.time()
        
        # Generate session_id if not provided
        session_id = request.session_id or f"session_{request.user_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Get or create session in MongoDB
            existing_session = get_session(session_id)
            if not existing_session:
                create_session(session_id, request.user_id)
                logger.info("Created new session in MongoDB: %s for user: %s", session_id, request.user_id)
            
            # Get conversation history from MongoDB
            messages = []
            if request.include_history:
                mongo_messages = get_session_messages(session_id, limit=10)
                for msg in mongo_messages[-6:]:  # Last 6 messages for context
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            # Add current query
            messages.append(HumanMessage(content=request.query))
            
            # Save user message to MongoDB
            add_message(session_id, "user", request.query)
            
            # Build and run graph
            graph = self._build_graph(request.user_id)
            result = graph.invoke({"messages": messages})
            
            result_messages = result.get("messages", [])
            response_text = self._extract_final_ai_message(result_messages)
            tools_used = self._extract_tools_used(result_messages)
            
            if not response_text:
                response_text = "I apologize, but I couldn't generate a response. Please try again."
                logger.warning("No AI response generated for query: %s", request.query[:50])
            
            # Save assistant response to MongoDB
            add_message(
                session_id,
                "assistant",
                response_text,
                metadata={"tools_used": tools_used}
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            logger.info(
                "Query processed - user: %s, session: %s, tools: %s, time: %.2fms",
                request.user_id, session_id, tools_used, execution_time
            )
            
            return AgentResponse(
                response=response_text,
                session_id=session_id,
                user_id=request.user_id,
                tools_used=tools_used,
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(
                "Agent error for user %s: %s",
                request.user_id,
                str(e),
                exc_info=True
            )
            execution_time = (time.time() - start_time) * 1000
            return AgentResponse(
                response="I apologize, but I encountered an error processing your request.",
                session_id=session_id,
                user_id=request.user_id,
                tools_used=[],
                execution_time_ms=execution_time,
                error=str(e),
            )


# Global agent instance
_agent_instance: Optional[RetailAgentMongo] = None


def get_agent_mongo() -> RetailAgentMongo:
    """Get or create the global agent instance with MongoDB persistence."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = RetailAgentMongo()
    return _agent_instance
