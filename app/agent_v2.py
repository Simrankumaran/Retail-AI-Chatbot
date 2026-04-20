"""Improved agent with session support, type safety, and multi-user capability."""
from typing import Optional, Dict, List, Any
import logging
import time
import json
from datetime import datetime

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.llm import load_llm
from app.tools.product import product_tool_list
from app.tools.order import order_tool_list
from app.tools.return_policy import return_policy_tool_list
from app.models import AgentRequest, AgentResponse, ChatSession, ChatMessage, MessageRole, ToolCallResult

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


class RetailAgent:
    """Enhanced retail assistant agent with session management."""
    
    def __init__(self):
        """Initialize the agent."""
        self.llm = load_llm()
        self.tools = [
            *product_tool_list,
            *order_tool_list,
            *return_policy_tool_list,
        ]
        self.sessions: Dict[str, ChatSession] = {}
        logger.info("RetailAgent initialized with %d tools", len(self.tools))
    
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
        
        def agent_fn(state: MessagesState) -> Dict[str, List]:
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
    
    def _check_not_found(self, tool_output: Any) -> bool:
        """Recursively check tool output for 'found: False'."""
        if isinstance(tool_output, dict):
            if not tool_output.get("found", True):
                return True
            for val in tool_output.values():
                if isinstance(val, list):
                    for item in val:
                        if self._check_not_found(item):
                            return True
        elif isinstance(tool_output, list):
            for item in tool_output:
                if self._check_not_found(item):
                    return True
        return False
    
    def get_or_create_session(self, session_id: str, user_id: str) -> ChatSession:
        """Get existing session or create a new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession(
                session_id=session_id,
                user_id=user_id,
            )
            logger.info("Created new session: %s for user: %s", session_id, user_id)
        return self.sessions[session_id]
    
    def add_message_to_session(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a message to session history."""
        if session_id in self.sessions:
            message = ChatMessage(role=role, content=content, metadata=metadata)
            self.sessions[session_id].messages.append(message)
            self.sessions[session_id].updated_at = datetime.utcnow()
    
    def get_session_history(self, session_id: str) -> List[ChatMessage]:
        """Get conversation history for a session."""
        if session_id in self.sessions:
            return self.sessions[session_id].messages
        return []
    
    def run(self, request: AgentRequest) -> AgentResponse:
        """
        Process a user query with full context awareness.
        
        Args:
            request: AgentRequest with query, user_id, and optional session_id
            
        Returns:
            AgentResponse with answer and metadata
        """
        start_time = time.time()
        session_id = request.session_id or f"session_{request.user_id}_{int(time.time())}"
        
        try:
            # Get or create session
            session = self.get_or_create_session(session_id, request.user_id)
            
            # Add user message to history
            self.add_message_to_session(
                session_id,
                MessageRole.USER,
                request.query
            )
            
            # Build conversation context if needed
            messages = []
            if request.include_history and len(session.messages) > 1:
                # Include last N messages for context (excluding the current one)
                for msg in session.messages[-6:-1]:  # Last 5 messages before current
                    if msg.role == MessageRole.USER:
                        messages.append(HumanMessage(content=msg.content))
                    elif msg.role == MessageRole.ASSISTANT:
                        messages.append(AIMessage(content=msg.content))
            
            # Add current query
            messages.append(HumanMessage(content=request.query))
            
            # Build and run graph
            graph = self._build_graph(request.user_id)
            result = graph.invoke({"messages": messages})
            
            result_messages = result.get("messages", [])
            response_text = self._extract_final_ai_message(result_messages)
            tools_used = self._extract_tools_used(result_messages)
            
            if not response_text:
                response_text = "I apologize, but I couldn't generate a response. Please try again."
                logger.warning("No AI response generated for query: %s", request.query[:50])
            
            # Add assistant response to history
            self.add_message_to_session(
                session_id,
                MessageRole.ASSISTANT,
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
_agent_instance: Optional[RetailAgent] = None


def get_agent() -> RetailAgent:
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = RetailAgent()
    return _agent_instance
