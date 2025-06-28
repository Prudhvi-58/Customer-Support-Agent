"""Deployment script for Car Support Agent"""
import os
import vertexai
from absl import app, flags
from dotenv import load_dotenv
from car_support_agent.agent import car_support_agent
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

FLAGS = flags.FLAGS

# Command line flags
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP bucket for staging.")
flags.DEFINE_string("resource_id", None, "AgentEngine resource ID.")
flags.DEFINE_bool("list", False, "List all agents.")
flags.DEFINE_bool("create", False, "Creates a new agent.")
flags.DEFINE_bool("delete", False, "Deletes an existing agent.")
flags.DEFINE_bool("update", False, "Updates an existing agent.")

# Ensure mutually exclusive operations
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete", "update"])

def create() -> None:
    """Creates an agent engine for Car Support Agent."""
    print("🚗 Creating Car Support Agent in Vertex AI Agent Engine...")
    
    try:
        # Create ADK app wrapper
        adk_app = AdkApp(
            agent=car_support_agent, 
            enable_tracing=True
        )
        
        # Create remote agent with specific requirements
        remote_agent = agent_engines.create(
            adk_app,
            display_name="Ford Car Support Agent",
            description="Intelligent car support agent for Ford vehicle inquiries, orders, and specifications",
            requirements=[
                # Core ADK requirements
                "google-adk>=0.0.2",
                "google-cloud-aiplatform[agent_engines]>=1.91.0,!=1.92.0",
                "google-genai>=1.5.0,<2.0.0",
                "pydantic>=2.10.6,<3.0.0",
                "absl-py>=2.2.1,<3.0.0",
                
                # Car Support Agent specific requirements
                "google-cloud-bigquery>=3.11.0",
                "google-auth>=2.23.0",
                "pandas>=1.5.0",
                "python-dotenv>=1.0.0",
                
                # Additional utilities
                "colorlog>=6.7.0",
            ],
            # Add extra packages if needed
            extra_packages=["car_support_agent"],
        )
        
        print(f"✅ Successfully created remote agent!")
        print(f"📋 Agent Resource Name: {remote_agent.resource_name}")
        print(f"🌐 Agent Name: {remote_agent.name}")
        print(f"📝 Display Name: {remote_agent.display_name}")
        
        # Extract agent ID for .env configuration
        resource_parts = remote_agent.resource_name.split('/')
        if len(resource_parts) >= 6:
            agent_id = resource_parts[-1]
            print(f"\n🔧 Configuration Update Needed:")
            print(f"Add this to your .env file:")
            print(f"VERTEX_AI_AGENT_ID={agent_id}")
        
        return remote_agent
        
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        raise

def update(resource_id: str) -> None:
    """Updates an existing agent engine."""
    print(f"🔄 Updating Car Support Agent: {resource_id}")
    
    try:
        # Get existing agent
        remote_agent = agent_engines.get(resource_id)
        
        # Create updated ADK app
        adk_app = AdkApp(
            agent=car_support_agent, 
            enable_tracing=True
        )
        
        # Update the agent
        updated_agent = remote_agent.update(
            adk_app=adk_app,
            display_name="Ford Car Support Agent",
            description="Intelligent car support agent for Ford vehicle inquiries, orders, and specifications",
        )
        
        print(f"✅ Successfully updated agent!")
        print(f"📋 Agent Resource Name: {updated_agent.resource_name}")
        print(f"🕒 Update Time: {updated_agent.update_time}")
        
        return updated_agent
        
    except Exception as e:
        print(f"❌ Failed to update agent: {e}")
        raise

def delete(resource_id: str) -> None:
    """Deletes an existing agent engine."""
    print(f"🗑️  Deleting Car Support Agent: {resource_id}")
    
    try:
        remote_agent = agent_engines.get(resource_id)
        agent_name = remote_agent.display_name
        
        # Confirm deletion
        print(f"⚠️  About to delete: {agent_name}")
        confirmation = input("Type 'DELETE' to confirm: ")
        
        if confirmation != 'DELETE':
            print("❌ Deletion cancelled.")
            return
        
        remote_agent.delete(force=True)
        print(f"✅ Successfully deleted agent: {resource_id}")
        
    except Exception as e:
        print(f"❌ Failed to delete agent: {e}")
        raise

def list_agents() -> None:
    """Lists all agent engines in the project."""
    print("📋 Listing all Car Support Agents...")
    
    try:
        remote_agents = agent_engines.list()
        
        if not remote_agents:
            print("No agents found in this project.")
            return
        
        template = """
🤖 {agent.display_name}
   Name: {agent.name}
   Resource ID: {resource_id}
   Created: {agent.create_time}
   Updated: {agent.update_time}
   Status: {status}
"""
        
        for agent in remote_agents:
            # Extract resource ID from resource name
            resource_id = agent.resource_name.split('/')[-1] if agent.resource_name else 'Unknown'
            status = "Active" if hasattr(agent, 'state') else "Unknown"
            
            agent_info = template.format(
                agent=agent, 
                resource_id=resource_id,
                status=status
            )
            print(agent_info)
            
    except Exception as e:
        print(f"❌ Failed to list agents: {e}")
        raise

def check_bigquery_setup(project_id: str) -> bool:
    """Check if BigQuery setup is working."""
    print("🔍 Checking BigQuery setup...")
    
    try:
        from car_support_agent.database.bigquery_manager import bigquery_manager
        
        # Test basic connectivity
        models = bigquery_manager.get_all_available_models()
        print(f"✅ BigQuery connection working - Found {len(models)} vehicle models")
        return True
        
    except Exception as e:
        print(f"❌ BigQuery setup issue: {e}")
        print("💡 Run 'python deployment/setup.py' to fix BigQuery setup")
        return False

def validate_agent() -> bool:
    """Validate that the agent is properly configured."""
    print("🔍 Validating agent configuration...")
    
    try:
        # Check if agent exists
        if not car_support_agent:
            print("❌ car_support_agent not found")
            return False
        
        print(f"✅ Agent found: {car_support_agent.name}")
        
        # Check agent components
        if hasattr(car_support_agent, 'tools'):
            print(f"✅ Tools: {len(car_support_agent.tools)} configured")
        
        if hasattr(car_support_agent, 'sub_agents'):
            print(f"✅ Sub-agents: {len(car_support_agent.sub_agents)} configured")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent validation failed: {e}")
        return False

def main(argv: list[str]) -> None:
    """Main deployment function."""
    del argv  # unused
    
    # Load environment variables
    load_dotenv()
    
    print("🚗 Ford Car Support Agent - Vertex AI Deployment")
    print("=" * 60)
    
    # Get configuration from flags or environment
    project_id = (
        FLAGS.project_id
        if FLAGS.project_id
        else os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    location = (
        FLAGS.location 
        if FLAGS.location 
        else os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    # Updated: Get bucket from environment variable first
    bucket = (
        FLAGS.bucket
        if FLAGS.bucket
        else os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET") or 
        os.getenv("STAGING_BUCKET") or 
        f"{project_id}-car-agent-staging"
    )
    
    # Display configuration
    print(f"📋 Configuration:")
    print(f"   Project ID: {project_id}")
    print(f"   Location: {location}")
    print(f"   Staging Bucket: gs://{bucket}")
    print()
    
    # Validate required configuration
    if not project_id:
        print("❌ Missing required environment variable: GOOGLE_CLOUD_PROJECT")
        print("💡 Set it in your .env file or use --project_id flag")
        return
    elif not location:
        print("❌ Missing required environment variable: GOOGLE_CLOUD_LOCATION")
        print("💡 Set it in your .env file or use --location flag")
        return
    
    # Initialize Vertex AI
    try:
        vertexai.init(
            project=project_id,
            location=location,
            staging_bucket=f"gs://{bucket}",
        )
        print("✅ Vertex AI initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI: {e}")
        return
    
    # Execute requested operation
    try:
        if FLAGS.list:
            list_agents()
            
        elif FLAGS.create:
            # Validate prerequisites
            if not validate_agent():
                print("❌ Agent validation failed. Please fix issues before deployment.")
                return
            
            if not check_bigquery_setup(project_id):
                print("❌ BigQuery setup failed. Please fix before deployment.")
                return
            
            print("✅ Prerequisites validated. Creating agent...")
            agent = create()
            
            if agent:
                print("\n🎉 Deployment successful!")
                print("\n📋 Next steps:")
                print("1. Update your .env file with the VERTEX_AI_AGENT_ID")
                print("2. Test the deployed agent")
                print("3. Configure any additional integrations")
            
        elif FLAGS.update:
            if not FLAGS.resource_id:
                print("❌ resource_id is required for update")
                print("💡 Use --resource_id flag or get ID from --list")
                return
            
            if not validate_agent():
                print("❌ Agent validation failed. Please fix issues before update.")
                return
            
            update(FLAGS.resource_id)
            
        elif FLAGS.delete:
            if not FLAGS.resource_id:
                print("❌ resource_id is required for delete")
                print("💡 Use --resource_id flag or get ID from --list")
                return
            
            delete(FLAGS.resource_id)
            
        else:
            print("❌ No operation specified")
            print("\n📋 Available operations:")
            print("   --create     Create a new agent")
            print("   --update     Update an existing agent")
            print("   --delete     Delete an existing agent")
            print("   --list       List all agents")
            print("\n💡 Example: python deployment/deploy.py --create")
            
    except Exception as e:
        print(f"❌ Operation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    app.run(main)