import os
import sys
import logging
import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines
import traceback
import uuid # Import for generating unique IDs

# --- Hide verbose dependency logs ---
#logging.getLogger("google_adk").setLevel(logging.WARNING)
#logging.getLogger("google_genai").setLevel(logging.WARNING)
#logging.getLogger("httpx").setLevel(logging.WARNING)
# ----------------------------------------

def extract_clean_response(event):
    """Extract clean text response from agent event, which is a dictionary."""
    try:
        # The stream_query() method returns a stream of dictionaries.
        text = event.get('content', {}).get('parts', [{}])[0].get('text')
        if text:
            return text.strip()
        return None
    except (IndexError, TypeError):
        return None

def main():
    """
    Runs a local, interactive, back-and-forth chat session with a DEPLOYED Car Support Agent.
    """
    # --- 1. INITIALIZATION ---
    load_dotenv()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    agent_id = os.getenv("VERTEX_AI_AGENT_ID")

    if not all([project_id, location, agent_id]):
        print("❌ Missing required environment variables: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, VERTEX_AI_AGENT_ID")
        sys.exit(1)

    print(f"🔄 Initializing Vertex AI...")
    vertexai.init(project=project_id, location=location)

    print(f"🔗 Connecting to deployed agent: {agent_id}...")
    try:
        # Get the remote agent instance
        remote_agent = agent_engines.get(agent_id)
    except Exception as e:
        print(f"❌ Failed to connect to the Agent Engine. Please check if the AGENT_ID is correct and the agent is deployed successfully.")
        print(f"   Error details: {e}")
        sys.exit(1)

    # --- Session Management ---
    # Generate a unique user_id for this chat session run.
    # This ensures a fresh context for each interactive session you start.
    chat_user_id = f"interactive_chat_user_{uuid.uuid4()}" 
    print(f"🤝 Starting conversation for ephemeral user: {chat_user_id}")

    current_session = None
    try:
        # Create a new session for this user.
        # This will get a fresh session ID from the deployed Reasoning Engine.
        print("💡 Creating a new session...")
        current_session = remote_agent.create_session(user_id=chat_user_id)
        # The 'current_session' object is a dictionary or similar object, with 'id' as the key for the session ID
        print(f"✅ Session created: {current_session['id']}")
    except Exception as e:
        print(f"❌ Failed to create a new session. This is a critical error for conversation state.")
        print(f"   Error details: {e}")
        sys.exit(1)

    print("✅ Agent is ready. Let's chat!")
    print("\n=======================================================")
    print("   Type your message and press Enter.")
    print("   Type 'quit' or 'exit' to end the conversation.")
    print("=======================================================")

    # --- 2. CONVERSATION LOOP ---
    try:
        while True:
            user_message = input("You: ").strip()

            if user_message.lower() in ["quit", "exit"]:
                print("🤖 Agent: Goodbye!")
                break

            if not user_message:
                continue

            print("🤖 Agent: ", end="", flush=True)
            
            full_response = ""
            
            # Use remote_agent.stream_query() and explicitly pass the session_id
            response_stream = remote_agent.stream_query(
                user_id=chat_user_id, # User ID associated with the session
                session_id=current_session['id'], # The explicit session ID for this conversation
                message=user_message,
            )

            for event in response_stream:
                clean_text = extract_clean_response(event)
                if clean_text:
                    print(clean_text, end="", flush=True)
                    full_response += clean_text
            
            print("\n")

    except KeyboardInterrupt:
        print("\n🤖 Agent: Conversation cancelled.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during chat: {e}")
        print("--- Full Error Traceback ---")
        traceback.print_exc()
        print("----------------------------")
    finally:
        # --- 3. Clean up: Delete the session when the conversation ends ---
        if current_session:
            try:
                print(f"🗑️ Deleting session: {current_session['id']}...")
                remote_agent.delete_session(user_id=chat_user_id, session_id=current_session['id'])
                print("✅ Session deleted.")
            except Exception as e:
                print(f"❌ Failed to delete session {current_session['id']}: {e}")

    print("\n=======================================================")
    print("🏁 Chat ended.")


if __name__ == "__main__":
    main()
