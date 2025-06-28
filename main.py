import os
import sys
import logging
from typing import Dict, Tuple

import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware 
# --- Configuration & Global Initialization ---
# Load environment variables
load_dotenv()

# Configure logging for the FastAPI application itself
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CarSupportAgentAPI")

# Configuration from environment variables
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
AGENT_ID = os.getenv("VERTEX_AI_AGENT_ID")

# Validate environment variables at startup
if not all([PROJECT_ID, LOCATION, AGENT_ID]):
    logger.error("Missing GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, or VERTEX_AI_AGENT_ID environment variables.")
    sys.exit(1)

# Initialize Vertex AI client globally when the app starts
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    logger.info(f"Vertex AI initialized for project: {PROJECT_ID}, location: {LOCATION}")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    sys.exit(1)

# Get the remote agent instance once globally when the app starts
try:
    REMOTE_AGENT = agent_engines.get(AGENT_ID)
    logger.info(f"Successfully connected to deployed agent: {AGENT_ID}")
except Exception as e:
    logger.error(f"Failed to connect to the Agent Engine at startup. Please check AGENT_ID and deployment status: {e}")
    sys.exit(1)


ACTIVE_CHATS: Dict[str, str] = {} # Mapping session_id to user_id

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Car Support Agent API",
    description="API for interacting with the Vertex AI Car Support Agent.",
    version="1.0.0",
)

origins = [
    "http://localhost:3000",   
    "http://127.0.0.1:3000",  
    
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      
    allow_credentials=True,     
    allow_methods=["*"],         
    allow_headers=["*"],         
)

# --- Pydantic Models for Request/Response Bodies ---
class StartChatResponse(BaseModel):
    session_id: str 
    message: str = "Chat session started."

class MessageRequest(BaseModel):
    message: str

class EndChatResponse(BaseModel):
    message: str


# --- Helper Function for Extracting Agent Response Text ---
def extract_clean_response(event) -> str | None:
    """Extract clean text response from a Vertex AI Reasoning Engine stream event."""
    try:
        text = event.get('content', {}).get('parts', [{}])[0].get('text')
        if text:
            return text.strip()
        return None
    except (IndexError, TypeError):
        return None

# --- API Endpoints ---

@app.post("/session/start", response_model=StartChatResponse, summary="Start a new chat session")
async def start_session(): 
    """
    Initiates a new chat session with the Car Support Agent.
    Returns the Vertex AI session_id for the client to use for subsequent interactions.
    """
    user_id = f"api_user_{uuid.uuid4()}" 
    
    try:
        # Create a new session with the deployed Vertex AI Reasoning Engine (synchronous call)
        session_obj = REMOTE_AGENT.create_session(user_id=user_id)
        session_id = session_obj['id']
        
        # Store the mapping: Vertex AI session_id -> internal user_id
        ACTIVE_CHATS[session_id] = user_id
        
        logger.info(f"New chat session started. session_id: {session_id}, user_id: {user_id}")
        return StartChatResponse(session_id=session_id) # Return the Vertex AI session_id
    except Exception as e:
        logger.error(f"Failed to create new session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start chat session. Please try again later or check agent deployment."
        )

@app.post("/session/{session_id}/message", summary="Send a message and get agent's response")
async def send_message(session_id: str, request: MessageRequest):
    """
    Sends a message to an active chat session and streams the agent's response back.
    """
    # Retrieve user_id using session_id
    user_id = ACTIVE_CHATS.get(session_id)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found. Please start a new session."
        )
    
    logger.info(f"Received message for session_id {session_id}: '{request.message}'")

    async def event_generator():
        try:
            # Call the synchronous method. No 'await' here.
            response_stream = REMOTE_AGENT.stream_query( 
                user_id=user_id,
                session_id=session_id,
                message=request.message,
            )
            
            # Use a regular 'for' loop to iterate over the synchronous generator.
            for event in response_stream: 
                clean_text = extract_clean_response(event)
                if clean_text:
                    yield f"data: {clean_text}\n\n"
        except Exception as e:
            logger.error(f"Error streaming message for session_id {session_id}: {e}", exc_info=True)
            yield f"data: ERROR: An internal error occurred during response generation. ({e})\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/session/{session_id}/end", response_model=EndChatResponse, summary="End a chat session")
async def end_session(session_id: str): # Changed path and parameter name
    """
    Terminates an active chat session and cleans up resources on the Vertex AI backend.
    """
    # Remove from active chats, getting user_id
    user_id = ACTIVE_CHATS.pop(session_id, None)
    if not user_id: # If session_id not found in map
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found or already ended."
        )
    
    try:
        # Delete the corresponding session on the Vertex AI backend (synchronous call)
        REMOTE_AGENT.delete_session(user_id=user_id, session_id=session_id)
        logger.info(f"Chat session {session_id} ended and deleted remotely.")
        return EndChatResponse(message="Chat session ended.")
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end chat session gracefully. Resources might still exist remotely."
        )