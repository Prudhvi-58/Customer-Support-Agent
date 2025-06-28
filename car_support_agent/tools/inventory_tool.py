"""
Inventory Search Tool for Car Support Agent

This tool handles all inventory-related queries:
- Vehicle availability checks
- Price inquiries
- Stock quantity requests
- Delivery time questions
- Model specifications

Uses BigQuery for data retrieval with intelligent search and response formatting.
"""

from google.adk.tools.tool_context import ToolContext
from car_support_agent.database.bigquery_manager import bigquery_manager
import logging
import difflib

logger = logging.getLogger(__name__)

def search_inventory(user_input: str, tool_context: ToolContext) -> dict:
    """
    Search inventory based on user query
    
    Handles queries like:
    - "Is Mustang available?"
    - "What's the price of Explorer EV?"
    - "How many Broncos are in stock?"
    - "When can I get a Maverick?"
    
    Args:
        user_input: User's search query
        tool_context: Tool execution context
        
    Returns:
        Structured response with vehicle information
    """
    logger.info(f"Inventory search request: '{user_input}'")
    print("123")
    try:
        # Clean and normalize user input
        user_input_lower = user_input.lower().strip()
        print("***",user_input_lower)
        # Remove common query words to focus on car model
        query_words = ["is", "the", "available", "in", "stock", "price", "cost", "how", 
                       "much", "does", "what", "when", "can", "get", "delivery", "time", 
                       "many", "units", "do", "you", "have", "ford"]
        
        cleaned_input = user_input_lower
        for word in query_words:
            cleaned_input = cleaned_input.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
        cleaned_input = cleaned_input.strip()
        
        logger.info(f"Cleaned search term: '{cleaned_input}'")
        
        if not cleaned_input:
            return _format_no_query_response()
        
        # Determine query type for response formatting
        query_type = _detect_query_type(user_input_lower)
        
        # Search for vehicles
        vehicles = bigquery_manager.search_inventory(cleaned_input, limit=5)
        
        if not vehicles:
            return _format_no_results_response(user_input, cleaned_input)
        
        # Get the best match (first result from ranked search)
        best_match = vehicles[0]
        
        # Format response based on query type
        return _format_vehicle_response(best_match, query_type, len(vehicles) > 1)
        
    except Exception as e:
        logger.error(f"Error in inventory search: {e}")
        return {
            "status": "error",
            "message": "I'm having trouble accessing our inventory system right now. Please try again in a moment."
        }

def _detect_query_type(user_input: str) -> str:
    """
    Detect what type of information the user is asking for
    
    Returns: 'availability', 'price', 'quantity', 'delivery', or 'general'
    """
    user_input = user_input.lower()
    
    # Availability queries
    if any(word in user_input for word in ["available", "in stock", "have"]):
        return "availability"
    
    # Price queries
    if any(word in user_input for word in ["price", "cost", "much", "expensive"]):
        return "price"
    
    # Quantity queries
    if any(word in user_input for word in ["how many", "quantity", "units"]):
        return "quantity"
    
    # Delivery queries
    if any(word in user_input for word in ["delivery", "when", "get", "receive"]):
        return "delivery"
    
    # General information
    return "general"

def _format_vehicle_response(vehicle: dict, query_type: str, multiple_matches: bool) -> dict:
    """
    Format vehicle information based on query type - IMPROVED for cleaner responses
    
    Args:
        vehicle: Vehicle data from BigQuery
        query_type: Type of query detected
        multiple_matches: Whether there were multiple search results
        
    Returns:
        Formatted response dictionary
    """
    model = vehicle["model"]
    price = vehicle["price"]
    stock = vehicle["stock"]
    delivery_days = vehicle["delivery_days"]
    
    # Format price
    price_formatted = f"${price / 100:,.0f}"
    
    # Base vehicle info
    base_info = {
        "status": "found",
        "model": model,
        "price": price,
        "stock": stock,
        "delivery_days": delivery_days,
        "in_stock": stock > 0
    }
    
    # Generate response message based on query type - SIMPLIFIED FOR OUT OF STOCK
    if query_type == "availability":
        if stock > 0:
            message = f"Yes, we have the {model} in stock! We currently have {stock} units available."
        else:
            message = f"No, the {model} is currently out of stock."
    
    elif query_type == "price":
        if stock > 0:
            message = f"The {model} is priced at {price_formatted}. We have {stock} units available."
        else:
            message = f"The {model} is currently out of stock. The price is {price_formatted}."
    
    elif query_type == "quantity":
        if stock > 0:
            message = f"We have {stock} {model} units available."
        else:
            message = f"The {model} is currently out of stock."
    
    elif query_type == "delivery":
        if stock > 0:
            message = f"The estimated delivery time for the {model} is {delivery_days} days."
        else:
            message = f"The {model} is currently out of stock. Delivery would be {delivery_days} days when restocked."
    
    else:  # general
        if stock > 0:
            message = (f"The {model} is available! "
                      f"Price: {price_formatted}, "
                      f"Stock: {stock} units, "
                      f"Delivery: {delivery_days} days.")
        else:
            # SIMPLIFIED: Just say it's out of stock for general queries
            message = f"The {model} is currently out of stock."
    
    # Add suggestion if there were multiple matches (only for in-stock items)
    if multiple_matches and stock > 0 and query_type in ["availability", "general"]:
        message += " Would you like me to check other similar models?"
    elif multiple_matches and stock == 0:
        message += " Would you like me to check other available models?"
    
    base_info["message"] = message
    return base_info

def _format_no_results_response(original_query: str, cleaned_query: str) -> dict:
    """Format response when no vehicles are found"""
    try:
        # Get available models for suggestions
        available_models = bigquery_manager.get_all_available_models()
        
        # Try to suggest similar models
        suggestions = []
        if cleaned_query and available_models:
            # Remove duplicates from available models
            unique_models = list(set(available_models))
            potential_matches = difflib.get_close_matches(
                cleaned_query, 
                [model.lower() for model in unique_models], 
                n=3, 
                cutoff=0.3
            )
            
            for match in potential_matches:
                for model in unique_models:
                    if model.lower() == match:
                        suggestions.append(model)
                        break
        
        message = f"I couldn't find '{original_query}' in our inventory."
        
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        elif available_models:
            # Show some available models
            unique_available = list(set(available_models))[:5]
            message += f" Available models include: {', '.join(unique_available)}."
        
        return {
            "status": "not_found",
            "message": message,
            "suggestions": suggestions,
            "available_models": list(set(available_models))
        }
        
    except Exception as e:
        logger.error(f"Error formatting no results response: {e}")
        return {
            "status": "not_found",
            "message": f"I couldn't find '{original_query}' in our inventory. Please try a different model name."
        }

def _format_no_query_response() -> dict:
    """Format response when no search term is provided"""
    try:
        available_models = bigquery_manager.get_all_available_models()
        unique_models = list(set(available_models))[:8]  # Show up to 8 unique models
        
        message = "What vehicle are you looking for? "
        if unique_models:
            message += f"Available models include: {', '.join(unique_models)}."
        
        return {
            "status": "no_query",
            "message": message,
            "available_models": unique_models
        }
        
    except Exception as e:
        logger.error(f"Error formatting no query response: {e}")
        return {
            "status": "no_query",
            "message": "What vehicle are you looking for? Please specify a Ford model."
        }

# ===================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ===================================================================

def get_vehicle_details(model: str) -> dict:
    """
    Get detailed information about a specific vehicle
    
    Args:
        model: Exact model name
        
    Returns:
        Vehicle details or error information
    """
    try:
        vehicle = bigquery_manager.get_vehicle_by_model(model)
        
        if not vehicle:
            return {
                "status": "not_found",
                "message": f"Vehicle '{model}' not found in inventory."
            }
        
        return _format_vehicle_response(vehicle, "general", False)
        
    except Exception as e:
        logger.error(f"Error getting vehicle details for '{model}': {e}")
        return {
            "status": "error",
            "message": "Error retrieving vehicle details."
        }

def check_availability(model: str) -> dict:
    """
    Quick availability check for a specific model
    
    Args:
        model: Vehicle model to check
        
    Returns:
        Availability status
    """
    try:
        vehicle = bigquery_manager.get_vehicle_by_model(model)
        
        if not vehicle:
            return {
                "status": "not_found",
                "available": False,
                "message": f"'{model}' not found in our inventory."
            }
        
        return {
            "status": "found",
            "model": vehicle["model"],
            "available": vehicle["stock"] > 0,
            "stock": vehicle["stock"],
            "message": f"{'Available' if vehicle['stock'] > 0 else 'Out of stock'}: {vehicle['model']}"
        }
        
    except Exception as e:
        logger.error(f"Error checking availability for '{model}': {e}")
        return {
            "status": "error",
            "available": False,
            "message": "Error checking vehicle availability."
        }