"""
Car Support Agent - Tools Module

This module provides all the tools that the car support agent uses:
- inventory_tool: Search inventory, check availability, get pricing
- order_tool: Create, confirm, cancel orders with session state management

These tools integrate with:
- BigQuery for persistent data storage
- VertexAI session service for conversation state
- Intelligent search and matching algorithms

Usage:
    from car_support_agent.tools.inventory_tool import search_inventory
    from car_support_agent.tools.order_tool import process_order_request
"""

from .inventory_tool import search_inventory, get_vehicle_details, check_availability
from .order_tool import process_order_request

# Make tools available at module level
__all__ = [
    'search_inventory',
    'get_vehicle_details', 
    'check_availability',
    'process_order_request'
]

# Version info
__version__ = '1.0.0'
__author__ = 'Car Support Agent Team'

# Tool metadata for agent registration
AVAILABLE_TOOLS = {
    "search_inventory": {
        "function": search_inventory,
        "description": "Search vehicle inventory, check availability, pricing, and delivery times",
        "parameters": {
            "user_input": {
                "type": "string",
                "description": "User's search query (e.g., 'is mustang available?', 'price of explorer ev')"
            }
        },
        "examples": [
            "Is the Mustang available?",
            "What's the price of Explorer EV?", 
            "How many Broncos are in stock?",
            "When can I get a Maverick?"
        ]
    },
    "process_order_request": {
        "function": process_order_request,
        "description": "Handle all order operations: create, confirm, cancel, and track orders",
        "parameters": {
            "user_input": {
                "type": "string", 
                "description": "User's order-related request (e.g., 'order mustang', 'yes', 'cancel my order')"
            }
        },
        "examples": [
            "Order a Mustang",
            "Yes, proceed with the booking",
            "Cancel my Explorer order",
            "Did you book my car?",
            "What's my order status?"
        ]
    }
}

def get_tool_info(tool_name: str) -> dict:
    """Get detailed information about a specific tool"""
    return AVAILABLE_TOOLS.get(tool_name, {})

def list_all_tools() -> list:
    """Get list of all available tool names"""
    return list(AVAILABLE_TOOLS.keys())

def validate_tools():
    """Validate that all tools are properly configured"""
    try:
        from car_support_agent.database.bigquery_manager import bigquery_manager
        
        if bigquery_manager is None:
            return {"status": "error", "message": "BigQuery manager not initialized"}
        
        # Test each tool
        results = {}
        
        # Test inventory search
        try:
            result = search_inventory("test", None)
            results["search_inventory"] = "OK" if result else "ERROR"
        except Exception as e:
            results["search_inventory"] = f"ERROR: {e}"
        
        # Test order processing  
        try:
            result = process_order_request("test", None)
            results["process_order_request"] = "OK" if result else "ERROR"
        except Exception as e:
            results["process_order_request"] = f"ERROR: {e}"
        
        return {"status": "success", "tools": results}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}