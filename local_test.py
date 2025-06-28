import os
import sys
import logging
import vertexai
from dotenv import load_dotenv
from vertexai.preview import reasoning_engines
from car_support_agent.agent import root_agent

# --- Hide verbose dependency logs ---
logging.getLogger("google_adk").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
# ----------------------------------------

def extract_clean_response(event):
    """Extract clean text response from agent event, which is a dictionary."""
    try:
        text = event.get('content', {}).get('parts', [{}])[0].get('text')
        if text:
            return text.strip()
        return None
    except (IndexError, TypeError):
        return None

def main():
    """
    Runs a local, interactive, back-and-forth chat session with the Car Support Agent.
    """
    # --- 1. INITIALIZATION ---
    load_dotenv()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")

    if not project_id or not location:
        print("❌ Missing required environment variables: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION")
        sys.exit(1)

    print(f"🔄 Initializing Vertex AI...")
    vertexai.init(project=project_id, location=location)

    print("🚗 Creating local Car Support Agent instance...")
    app = reasoning_engines.AdkApp(agent=root_agent, enable_tracing=False)

    print("🤝 Creating a new conversation session...")
    # This session will be used for the entire conversation
    session = app.create_session(user_id="interactive_chat_user")
    print("✅ Agent is ready. Let's chat!")
    print("\n=======================================================")
    print("   Type your message and press Enter.")
    print("   Type 'quit' or 'exit' to end the conversation.")
    print("=======================================================")

    # --- 2. CONVERSATION LOOP ---
    while True:
        try:
            # Get user input
            user_message = input("You: ").strip()

            # Check for exit condition
            if user_message.lower() in ["quit", "exit"]:
                print("🤖 Agent: Goodbye!")
                break # Exit the loop

            if not user_message:
                continue # If user just presses enter, loop again

            # Send message and get response
            print("🤖 Agent: ", end="", flush=True) # Print "Agent:" prompt immediately
            
            full_response = ""
            for event in app.stream_query(
                user_id=session.user_id,
                session_id=session.id, # Use the same session ID for context
                message=user_message,
            ):
                clean_text = extract_clean_response(event)
                if clean_text:
                    print(clean_text, end="", flush=True)
                    full_response += clean_text
            
            print("\n") # Add a newline after the agent's full response

        except KeyboardInterrupt:
            print("\n🤖 Agent: Conversation cancelled. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            continue

    # --- 3. CLEANUP ---
    print("\n=======================================================")
    print("🧹 Cleaning up session...")
    try:
        app.delete_session(user_id=session.user_id, session_id=session.id)
        print("✅ Session cleaned up successfully.")
    except Exception as e:
        print(f"⚠️ Could not clean up session: {e}")
    print("🏁 Chat ended.")


if __name__ == "__main__":
    main()