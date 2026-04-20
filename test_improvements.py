"""Test script to demonstrate improved agent features."""
import sys
sys.path.insert(0, 'c:\\Users\\INSIMUD1\\Documents\\AI\\Retail-AI-Chatbot')

from app.agent_v2 import get_agent
from app.models import AgentRequest

def test_multi_user_support():
    """Test that different users get personalized experiences."""
    print("=" * 60)
    print("TEST 1: Multi-User Support")
    print("=" * 60)
    
    agent = get_agent()
    
    # User 2001
    request1 = AgentRequest(
        query="Show me my recent orders",
        user_id="2001",
        session_id="test_session_2001"
    )
    response1 = agent.run(request1)
    print(f"\n👤 User 2001 Query: {request1.query}")
    print(f"🤖 Response: {response1.response[:200]}...")
    print(f"⏱️  Time: {response1.execution_time_ms:.2f}ms")
    
    # User 2002
    request2 = AgentRequest(
        query="Show me my recent orders",
        user_id="2002",
        session_id="test_session_2002"
    )
    response2 = agent.run(request2)
    print(f"\n👤 User 2002 Query: {request2.query}")
    print(f"🤖 Response: {response2.response[:200]}...")
    print(f"⏱️  Time: {response2.execution_time_ms:.2f}ms")


def test_session_continuity():
    """Test conversation history tracking."""
    print("\n" + "=" * 60)
    print("TEST 2: Session Continuity")
    print("=" * 60)
    
    agent = get_agent()
    session_id = "test_conversation"
    
    # First message
    request1 = AgentRequest(
        query="What laptops do you have?",
        user_id="2001",
        session_id=session_id
    )
    response1 = agent.run(request1)
    print(f"\n👤 User: {request1.query}")
    print(f"🤖 Assistant: {response1.response[:150]}...")
    
    # Follow-up message (with history)
    request2 = AgentRequest(
        query="Show me ones under 50k",
        user_id="2001",
        session_id=session_id,
        include_history=True
    )
    response2 = agent.run(request2)
    print(f"\n👤 User: {request2.query}")
    print(f"🤖 Assistant: {response2.response[:150]}...")
    
    # Get session history
    history = agent.get_session_history(session_id)
    print(f"\n📝 Session has {len(history)} messages")
    for i, msg in enumerate(history):
        print(f"   {i+1}. [{msg.role.value}]: {msg.content[:60]}...")


def test_type_safety():
    """Test Pydantic validation."""
    print("\n" + "=" * 60)
    print("TEST 3: Type Safety & Validation")
    print("=" * 60)
    
    agent = get_agent()
    
    # Valid request
    try:
        valid_request = AgentRequest(
            query="Test query",
            user_id="2001"
        )
        print("✅ Valid request accepted")
    except Exception as e:
        print(f"❌ Valid request failed: {e}")
    
    # Invalid user_id (not 4 digits)
    try:
        invalid_request = AgentRequest(
            query="Test query",
            user_id="123"  # Only 3 digits
        )
        print("❌ Invalid request accepted (should have failed!)")
    except Exception as e:
        print(f"✅ Invalid user_id rejected: {type(e).__name__}")
    
    # Empty query
    try:
        empty_query = AgentRequest(
            query="",
            user_id="2001"
        )
        print("❌ Empty query accepted (should have failed!)")
    except Exception as e:
        print(f"✅ Empty query rejected: {type(e).__name__}")


def test_metrics_and_logging():
    """Test that metrics are being tracked."""
    print("\n" + "=" * 60)
    print("TEST 4: Metrics & Observability")
    print("=" * 60)
    
    agent = get_agent()
    
    request = AgentRequest(
        query="What is your return policy?",
        user_id="2001",
        session_id="metrics_test"
    )
    
    response = agent.run(request)
    
    print(f"\n📊 Metrics:")
    print(f"   - Execution Time: {response.execution_time_ms:.2f}ms")
    print(f"   - Tools Used: {response.tools_used}")
    print(f"   - Session ID: {response.session_id}")
    print(f"   - User ID: {response.user_id}")
    print(f"   - Error: {response.error or 'None'}")


if __name__ == "__main__":
    print("\n🚀 Testing Improved Agent Features\n")
    
    try:
        test_multi_user_support()
        test_session_continuity()
        test_type_safety()
        test_metrics_and_logging()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
