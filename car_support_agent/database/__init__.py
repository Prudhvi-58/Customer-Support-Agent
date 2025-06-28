"""
Car Support Agent - Database Module

This module provides database operations for the car support agent:
- BigQuery integration for inventory and order management
- Automatic database setup and initialization
- Data validation and error handling

Usage:
    from car_support_agent.database import bigquery_manager
    
    # Search inventory
    vehicles = bigquery_manager.search_inventory("mustang")
    
    # Create order
    order = bigquery_manager.create_order("Mustang", user_name="John")
    
    # Confirm order
    success = bigquery_manager.confirm_order(order["order_id"])
"""

from .bigquery_manager import bigquery_manager

# Make the manager available at module level
__all__ = ['bigquery_manager']

# Version info
__version__ = '1.0.0'
__author__ = 'Car Support Agent Team'

# Module-level convenience functions
def get_database_status():
    """Get database connection status"""
    try:
        if bigquery_manager is None:
            return {"status": "disconnected", "error": "BigQuery Manager not initialized"}
        
        # Test connection by getting available models
        models = bigquery_manager.get_all_available_models()
        return {
            "status": "connected",
            "available_models": len(models),
            "models": models[:5]  # First 5 models
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def reset_database():
    """Reset database to default state (development only)"""
    try:
        if bigquery_manager is None:
            raise Exception("BigQuery Manager not initialized")
        
        # This would delete and recreate tables
        # Only implement if needed for development
        raise NotImplementedError("Database reset not implemented for safety")
        
    except Exception as e:
        raise Exception(f"Failed to reset database: {e}")