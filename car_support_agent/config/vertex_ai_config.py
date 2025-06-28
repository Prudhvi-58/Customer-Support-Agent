"""
Vertex AI Configuration for Car Support Agent

This file manages all configuration settings for:
- Vertex AI Agent Engine connection
- BigQuery database settings  
- Authentication and project settings
- Session management configuration
"""

import os
from typing import Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class VertexAIConfig:
    """
    Centralized configuration for Vertex AI Agent Engine deployment
    
    This class handles:
    1. Google Cloud project settings
    2. Vertex AI Agent Engine configuration
    3. BigQuery database configuration
    4. Session management settings
    5. Environment variable validation
    """
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        
        # === CORE GOOGLE CLOUD SETTINGS ===
        # These are required for any Vertex AI operation
        self.project_id: str = os.getenv('GOOGLE_CLOUD_PROJECT', '')
        self.location: str = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # === VERTEX AI AGENT ENGINE SETTINGS ===
        # Agent ID will be provided after we deploy the agent
        self.agent_id: Optional[str] = os.getenv('VERTEX_AI_AGENT_ID')
        
        # Model configuration - using Gemini models for best performance
        self.model_name: str = os.getenv('VERTEX_AI_MODEL', 'gemini-2.0-flash-001')
        
        # === DEPLOYMENT SETTINGS ===
        # Staging bucket for deployment (added for deployment script)
        self.staging_bucket: str = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET') or os.getenv('STAGING_BUCKET', f"{self.project_id}-car-agent-staging")
        
        # Environment type (local, development, staging, production)
        self.environment: str = os.getenv('ENVIRONMENT', 'local')
        
        # === AUTHENTICATION ===
        # Service account key file path (optional - can use Application Default Credentials)
        self.credentials_path: Optional[str] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Google API Key for search capabilities
        self.google_api_key: Optional[str] = os.getenv('GOOGLE_API_KEY')
        
        # === BIGQUERY CONFIGURATION ===
        # Dataset and table names for inventory and orders
        self.dataset_id: str = os.getenv('BIGQUERY_DATASET_ID', 'car_inventory')
        self.inventory_table_id: str = os.getenv('INVENTORY_TABLE_ID', 'vehicles')
        self.orders_table_id: str = os.getenv('ORDERS_TABLE_ID', 'customer_orders')
        
        # === SESSION CONFIGURATION ===
        # How long to keep session data (in seconds)
        self.session_ttl_seconds: int = int(os.getenv('SESSION_TTL_SECONDS', '3600'))  # 1 hour default
        
        # === LOGGING CONFIGURATION ===
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        
        # === VALIDATION ===
        # Check that required settings are provided
        self._validate_config()
        
        # === LOGGING SETUP ===
        self._setup_logging()
        
        logger.info("Vertex AI Configuration initialized successfully")
        logger.info(f"Project: {self.project_id}, Location: {self.location}, Environment: {self.environment}")
    
    def _validate_config(self):
        """
        Validate that all required configuration is present
        
        This prevents runtime errors by catching configuration issues early
        """
        errors = []
        warnings = []
        
        if not self.project_id:
            errors.append("GOOGLE_CLOUD_PROJECT environment variable is required")
        
        if not self.location:
            errors.append("GOOGLE_CLOUD_LOCATION environment variable is required")
        
        # Agent ID is optional initially (we'll get it after deployment)
        # But we'll warn if it's missing in production
        if not self.agent_id:
            if self.environment in ['production', 'staging']:
                warnings.append("VERTEX_AI_AGENT_ID not set - this is required for production deployments")
            else:
                logger.info("VERTEX_AI_AGENT_ID not set - this will be provided after deployment")
        
        # Check for API key if needed
        if not self.google_api_key and self.environment != 'local':
            warnings.append("GOOGLE_API_KEY not set - required for search functionality")
        
        # Validate BigQuery settings
        if not self.dataset_id:
            errors.append("BIGQUERY_DATASET_ID environment variable is required")
        
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            raise ValueError(error_message)
        
        if warnings:
            for warning in warnings:
                logger.warning(warning)
        
        logger.info("Configuration validation passed")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # === COMPUTED PROPERTIES ===
    # These generate full resource names from the basic configuration
    
    @property
    def agent_resource_name(self) -> str:
        """
        Get the full Vertex AI agent resource name
        
        Format: projects/{project}/locations/{location}/agents/{agent_id}
        This is used in API calls to identify your specific agent
        """
        if not self.agent_id:
            raise ValueError(
                "VERTEX_AI_AGENT_ID environment variable is required for agent operations. "
                "This will be provided after you deploy your agent to Vertex AI Agent Engine."
            )
        
        return f"projects/{self.project_id}/locations/{self.location}/agents/{self.agent_id}"
    
    @property
    def staging_bucket_uri(self) -> str:
        """
        Get the full GCS URI for staging bucket
        
        Format: gs://bucket-name
        This is used for Vertex AI deployment staging
        """
        return f"gs://{self.staging_bucket}"
    
    @property
    def inventory_table_full_id(self) -> str:
        """
        Get the full BigQuery table ID for inventory
        
        Format: project.dataset.table
        This is used in BigQuery SQL queries
        """
        return f"{self.project_id}.{self.dataset_id}.{self.inventory_table_id}"
    
    @property
    def orders_table_full_id(self) -> str:
        """
        Get the full BigQuery table ID for orders
        
        Format: project.dataset.table
        """
        return f"{self.project_id}.{self.dataset_id}.{self.orders_table_id}"
    
    @property
    def dataset_full_id(self) -> str:
        """
        Get the full BigQuery dataset ID
        
        Format: project.dataset
        """
        return f"{self.project_id}.{self.dataset_id}"
    
    # === UTILITY METHODS ===
    
    def is_local_development(self) -> bool:
        """
        Check if we're running in local development mode
        
        Returns True if running locally, False if in cloud environment
        """
        return self.environment == 'local'
    
    def is_production(self) -> bool:
        """
        Check if we're running in production mode
        
        Returns True if in production environment
        """
        return self.environment == 'production'
    
    def get_session_config(self) -> dict:
        """
        Get session configuration for VertexAISessionService
        
        Returns a dictionary with session settings
        """
        return {
            'project_id': self.project_id,
            'location': self.location,
            'session_ttl_seconds': self.session_ttl_seconds
        }
    
    def get_bigquery_config(self) -> dict:
        """
        Get BigQuery configuration
        
        Returns a dictionary with BigQuery settings
        """
        return {
            'project_id': self.project_id,
            'dataset_id': self.dataset_id,
            'inventory_table': self.inventory_table_full_id,
            'orders_table': self.orders_table_full_id,
            'location': self.location
        }
    
    def get_deployment_config(self) -> dict:
        """
        Get deployment configuration for Vertex AI Agent Engine
        
        Returns a dictionary with deployment settings
        """
        return {
            'project_id': self.project_id,
            'location': self.location,
            'staging_bucket': self.staging_bucket_uri,
            'environment': self.environment,
            'model_name': self.model_name
        }
    
    def validate_for_deployment(self) -> bool:
        """
        Validate configuration specifically for deployment
        
        Returns True if ready for deployment, raises ValueError if not
        """
        deployment_errors = []
        
        if not self.project_id:
            deployment_errors.append("GOOGLE_CLOUD_PROJECT is required for deployment")
        
        if not self.location:
            deployment_errors.append("GOOGLE_CLOUD_LOCATION is required for deployment")
        
        if not self.staging_bucket:
            deployment_errors.append("GOOGLE_CLOUD_STORAGE_BUCKET is required for deployment")
        
        if not self.dataset_id:
            deployment_errors.append("BIGQUERY_DATASET_ID is required for deployment")
        
        if deployment_errors:
            error_message = "Deployment validation failed:\n" + "\n".join(f"- {error}" for error in deployment_errors)
            raise ValueError(error_message)
        
        logger.info("Deployment validation passed")
        return True
    
    def __str__(self) -> str:
        """String representation for debugging"""
        return f"VertexAIConfig(project={self.project_id}, location={self.location}, agent={self.agent_id}, env={self.environment})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"VertexAIConfig("
                f"project_id='{self.project_id}', "
                f"location='{self.location}', "
                f"agent_id='{self.agent_id}', "
                f"environment='{self.environment}', "
                f"staging_bucket='{self.staging_bucket}'"
                f")")

# === GLOBAL CONFIGURATION INSTANCE ===
# This creates a single configuration instance that can be imported throughout the project
# Usage: from car_support_agent.config.vertex_ai_config import config
try:
    config = VertexAIConfig()
except Exception as e:
    logger.error(f"Failed to initialize configuration: {e}")
    # In development, we might want to continue with partial config
    if os.getenv('ENVIRONMENT') in ['development', 'local']:
        logger.warning("Continuing with partial configuration for development")
        config = None
    else:
        raise