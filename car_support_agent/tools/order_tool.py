from google.adk.tools.tool_context import ToolContext
from car_support_agent.database.bigquery_manager import bigquery_manager
import logging
import difflib
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

def process_order_request(user_input: str, tool_context: ToolContext) -> dict:
    
    logger.info(f"Order processing request: '{user_input}'")
    
    try:
        state = tool_context.state if hasattr(tool_context, 'state') else {}
        user_input_lower = user_input.lower().strip()
        
        session_id = getattr(tool_context, 'session_id', None) or str(uuid.uuid4())
        user_name = state.get('user_name', 'Customer')

        if state.get("pending_order") and _is_specific_confirmation_phrase(user_input_lower, state):
             logger.info("Detected specific confirmation phrase. Handling confirmation.")
             return _handle_confirmation(user_input_lower, state, session_id)
        
        elif _is_conversation_closer(user_input_lower):
            logger.info("Detected conversation closure request.")
            return _handle_conversation_close(state)
        
        elif _is_order_status_request(user_input_lower):
            logger.info("Detected order status request.")
            return _handle_order_status(state, session_id)
        
        elif _is_cancellation_request(user_input_lower, state):
            logger.info("Detected cancellation request.")
            return _handle_cancellation(user_input_lower, state, session_id)
        
        elif _is_new_order_request(user_input_lower):
            logger.info("Detected new order request.")
            return _handle_new_order(user_input, state, session_id, user_name)
        
        elif state.get("pending_order") and _is_generic_yes_confirmation(user_input_lower):
            pending_model = state["pending_order"]["model"]
            expected_phrase = state.get("pending_order_confirmation_phrase", f"Confirm order for {pending_model}")
            logger.info(f"Detected generic 'yes' for pending order. Prompting for specific phrase: '{expected_phrase}'")
            return {
                "status": "clarification_needed",
                "message": f"To finalize your order for the {pending_model}, please say: '{expected_phrase}'"
            }

        else:
            logger.info("Request is unclear or not covered by specific handlers.")
            return _handle_unclear_request(user_input)
    
    except Exception as e:
        logger.error(f"Critical error processing order request: {e}", exc_info=True)
        if "pending_order" in state:
            state["pending_order"] = None
            state["pending_order_confirmation_phrase"] = None
        return {
            "status": "error",
            "message": "I'm having trouble processing your request right now. Please try again."
        }

def _is_cancellation_request(user_input: str, state: dict) -> bool:
    cancel_phrases = [
        "cancel", "cancel my order", "cancel order", "cancel the order",
        "don't want", "do not want", "remove my order", "delete my order",
        "i changed my mind", "nevermind", "never mind"
    ]
    
    if state.get("awaiting_cancellation_clarification", False) and _extract_model_from_input(user_input):
        return True
    
    return any(phrase in user_input for phrase in cancel_phrases)

def _is_generic_yes_confirmation(user_input: str) -> bool:
    generic_confirm_phrases = ["yes", "yeah", "yep", "confirm", "proceed", "go ahead"]
    return any(phrase in user_input for phrase in generic_confirm_phrases)

def _is_specific_confirmation_phrase(user_input: str, state: dict) -> bool:
    expected_phrase = state.get("pending_order_confirmation_phrase")
    if not expected_phrase:
        return False
    
    matches = difflib.get_close_matches(user_input.lower(), [expected_phrase.lower()], n=1, cutoff=0.8)
    return bool(matches)

def _is_conversation_closer(user_input: str) -> bool:
    close_phrases = [
        "that's it", "thats it", "done", "finished", "thank you", 
        "thanks", "goodbye", "bye", "good bye", "see you later",
        "nothing else", "no more", "i'm done", "im done"
    ]
    return any(phrase in user_input for phrase in close_phrases)

def _is_order_status_request(user_input: str) -> bool:
    status_phrases = [
        "did you book", "order status", "my order", "what did i order",
        "check my order", "order confirmation", "my booking",
        "what cars did i order", "show my orders", "list my orders",
        "previous order", "last order", "order history", "my bookings", 
        "status of my order", "find my order", "where is my order" # Added more variations
    ]
    return any(phrase in user_input for phrase in status_phrases)

def _is_new_order_request(user_input: str) -> bool:
    order_phrases = ["order", "buy", "purchase", "book", "get", "want", "i need"]
    
    if (any(phrase in user_input for phrase in ["cancel", "don't want", "do not want"]) or
        _is_order_status_request(user_input)):
        return False
    
    return any(phrase in user_input for phrase in order_phrases)

def _handle_cancellation(user_input: str, state: dict, session_id: str) -> dict:
    try:
        if state.get("awaiting_cancellation_clarification", False) and _extract_model_from_input(user_input):
            logger.info("Handling cancellation clarification.")
            return _handle_cancellation_clarification(user_input, state, session_id)
        
        orders = bigquery_manager.get_orders_by_session(session_id)
        confirmed_orders_db = [o for o in orders if o["status"] == "confirmed"]
        session_orders_cache = state.get("ordered_cars", [])

        all_orders_for_cancellation = []
        for order in confirmed_orders_db:
            all_orders_for_cancellation.append({
                "order_id": order["order_id"],
                "model": order["model"],
                "price": order["price"],
                "source": "database"
            })
        
        for session_order in session_orders_cache:
            if not any(db_order["model"].lower() == session_order["model"].lower() 
                      for db_order in confirmed_orders_db):
                all_orders_for_cancellation.append({
                    "order_id": session_order.get("order_id"),
                    "model": session_order["model"],
                    "price": session_order["price"],
                    "source": "session"
                })
        
        if not all_orders_for_cancellation:
            state["awaiting_cancellation_clarification"] = False
            state["cancellation_options"] = []
            logger.info("No confirmed orders to cancel for this session.")
            return {
                "status": "no_orders",
                "message": "You don't have any confirmed orders to cancel."
            }
        
        model_to_cancel = _extract_model_from_input(user_input)
        
        if model_to_cancel:
            for order in all_orders_for_cancellation:
                if difflib.get_close_matches(model_to_cancel.lower(), [order["model"].lower()], n=1, cutoff=0.8):
                    logger.info(f"Attempting to cancel specific order: {order['model']}")
                    success = _cancel_specific_order(order, state, session_id)
                    state["awaiting_cancellation_clarification"] = False
                    state["cancellation_options"] = []
                    
                    if success:
                        return {
                            "status": "cancelled",
                            "message": f"✅ Your {order['model']} order has been cancelled successfully."
                        }
                    else:
                        return {
                            "status": "cancel_failed",
                            "message": f"I had trouble cancelling your {order['model']} order. Please contact customer service."
                        }
            
            available_models_text = ", ".join([order["model"] for order in all_orders_for_cancellation])
            logger.info(f"Model '{model_to_cancel}' mentioned for cancellation, but not found in existing orders.")
            return {
                "status": "model_not_found",
                "message": f"I couldn't find a {model_to_cancel} order. Your current confirmed orders are: {available_models_text}. Which one would you like to cancel?"
            }
        
        if len(all_orders_for_cancellation) == 1:
            order = all_orders_for_cancellation[0]
            logger.info(f"Only one confirmed order, cancelling it directly: {order['model']}")
            success = _cancel_specific_order(order, state, session_id)
            
            if success:
                return {
                    "status": "cancelled",
                    "message": f"✅ Your {order['model']} order has been cancelled successfully."
                }
            else:
                return {
                    "status": "cancel_failed",
                    "message": f"I had trouble cancelling your {order['model']} order. Please contact customer service."
                }
        
        order_list = ", ".join([order["model"] for order in all_orders_for_cancellation])
        state["awaiting_cancellation_clarification"] = True
        state["cancellation_options"] = all_orders_for_cancellation
        logger.info(f"Multiple confirmed orders, asking for clarification: {order_list}")
        return {
            "status": "clarification_needed",
            "message": f"You have multiple confirmed orders: {order_list}. Which vehicle would you like to cancel?"
        }
        
    except Exception as e:
        logger.error(f"Error handling full cancellation flow: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "I had trouble processing your cancellation request. Please try again."
        }

def _handle_cancellation_clarification(user_input: str, state: dict, session_id: str) -> dict:
    try:
        cancellation_options = state.get("cancellation_options", [])
        
        if not cancellation_options:
            state["awaiting_cancellation_clarification"] = False
            logger.warning("No cancellation options found in state, but clarification requested.")
            return {
                "status": "no_options",
                "message": "I don't see any orders available for cancellation. Please try again."
            }
        
        model_to_cancel = _extract_model_from_input(user_input)
        
        if model_to_cancel:
            for order in cancellation_options:
                if difflib.get_close_matches(model_to_cancel.lower(), [order["model"].lower()], n=1, cutoff=0.8):
                    logger.info(f"Clarification received: cancelling {order['model']}")
                    success = _cancel_specific_order(order, state, session_id)
                    state["awaiting_cancellation_clarification"] = False
                    state["cancellation_options"] = []
                    
                    if success:
                        return {
                            "status": "cancelled",
                            "message": f"✅ Your {order['model']} order has been cancelled successfully."
                        }
                    else:
                        return {
                            "status": "cancel_failed",
                            "message": f"I had trouble cancelling your {order['model']} order. Please contact customer service."
                        }
        
        available_models_text = ", ".join([order["model"] for order in cancellation_options])
        logger.info(f"Cancellation clarification unclear. Prompting again. Options: {available_models_text}")
        return {
            "status": "clarification_needed",
            "message": f"Please specify which vehicle you'd like to cancel from: {available_models_text}"
        }
        
    except Exception as e:
        logger.error(f"Error handling cancellation clarification: {e}", exc_info=True)
        state["awaiting_cancellation_clarification"] = False
        state["cancellation_options"] = []
        return {
            "status": "error",
            "message": "I had trouble processing your cancellation. Please try again."
        }

def _cancel_specific_order(order: dict, state: dict, session_id: str) -> bool:
    try:
        success = True
        
        if order.get("order_id") and order.get("source") == "database":
            logger.info(f"Calling BigQuery manager to cancel order ID: {order['order_id']}")
            success = bigquery_manager.cancel_order(order["order_id"])
        elif order.get("source") == "session":
            logger.info(f"Order {order['model']} was session-only, not cancelling in BigQuery.")
        
        ordered_cars = state.get("ordered_cars", [])
        filtered_ordered_cars = [
            car for car in ordered_cars 
            if not (car["model"].lower() == order["model"].lower() and
                    (not order.get("order_id") or car.get("order_id") == order.get("order_id")))
        ]
        state["ordered_cars"] = filtered_ordered_cars
        
        logger.info(f"Order for {order['model']} cancelled (db_status={success}). Remaining session orders: {state.get('ordered_cars', [])}")
        return success
        
    except Exception as e:
        logger.error(f"Error cancelling specific order: {e}", exc_info=True)
        return False

def _handle_confirmation(user_input: str, state: dict, session_id: str) -> dict:
    try:
        pending_order = state.get("pending_order")
        if not pending_order or not _is_specific_confirmation_phrase(user_input, state):
            logger.warning(f"Attempted _handle_confirmation without valid pending order or specific phrase. Input: {user_input}")
            return {
                "status": "no_pending_order",
                "message": "I don't see any pending order to confirm, or your confirmation was unclear. What would you like to order?"
            }
        
        orders_in_db = bigquery_manager.get_orders_by_session(session_id)
        orders_in_state = state.get("ordered_cars", [])
        
        existing_order = None
        for order in orders_in_db:
            if order["model"].lower() == pending_order["model"].lower() and order["status"] == "confirmed":
                existing_order = order
                break
        if not existing_order:
            for order in orders_in_state:
                if order["model"].lower() == pending_order["model"].lower():
                    existing_order = order
                    break
        
        if existing_order:
            logger.info(f"Order for {pending_order['model']} already exists ({existing_order.get('order_id', 'no_id')}). Avoiding duplicate creation.")
            state["pending_order"] = None
            state["pending_order_confirmation_phrase"] = None
            return {
                "status": "already_confirmed",
                "message": f"✅ Your {existing_order['model']} order is already confirmed! Is there anything else I can help you with?"
            }
        
        logger.info(f"Attempting to create confirmed order for {pending_order['model']} in BigQuery.")
        order = bigquery_manager.create_order(
            model=pending_order["model"],
            user_name=state.get("user_name", "Customer"),
            session_id=session_id
        )
        
        if not order:
            logger.error(f"BigQuery create_order failed for {pending_order['model']}. No order object returned from manager.")
            return {
                "status": "creation_failed",
                "message": f"I had trouble creating your {pending_order['model']} order. The vehicle might be out of stock (less likely with initial check) or an internal database error occurred."
            }
        
        stock_updated = bigquery_manager.update_stock(order["model"], -1)
        if not stock_updated:
            logger.warning(f"Failed to decrement stock for {order['model']} after order confirmation. Automatic stock reconciliation might be needed.")
        
        state["pending_order"] = None
        state["pending_order_confirmation_phrase"] = None

        ordered_cars = state.get("ordered_cars", [])
        ordered_cars.append({
            "order_id": order["order_id"],
            "model": order["model"],
            "price": order["price"],
            "delivery_days": order["delivery_days"]
        })
        state["ordered_cars"] = ordered_cars
        
        price_formatted = f"${order['price']/100:,.0f}"
        return {
            "status": "confirmed",
            "order_id": order["order_id"],
            "message": (
                f"✅ Excellent! Your {order['model']} has been reserved!\n\n"
                f"📋 Order Details:\n"
                f"• Vehicle: {order['model']}\n"
                f"• Price: {price_formatted}\n"
                f"• Order ID: {order['order_id']}\n"
                f"• Estimated Delivery: {order['delivery_days']} days\n\n"
                f"📍 Next Steps:\n"
                f"Please visit your nearest Ford dealership to complete payment and finalize the purchase.\n\n"
                f"Is there anything else I can help you with?"
            )
        }
        
    except Exception as e:
        logger.error(f"Critical error handling confirmation: {e}", exc_info=True)
        if "pending_order" in state:
            state["pending_order"] = None
            state["pending_order_confirmation_phrase"] = None
        return {
            "status": "error",
            "message": "I had trouble confirming your order. Please try again."
        }

def _handle_conversation_close(state: dict) -> dict:
    if "pending_order" in state:
        state["pending_order"] = None
    if "awaiting_cancellation_clarification" in state:
        state["awaiting_cancellation_clarification"] = False
    if "cancellation_options" in state:
        state["cancellation_options"] = []
    
    logger.info("Conversation closing, clearing all order-related session state.")
    return {
        "status": "conversation_complete",
        "message": "Perfect! Thank you for choosing Ford. Have a great day! 🚗"
    }

def _handle_order_status(state: dict, session_id: str) -> dict:
    try:
        orders_from_bigquery = bigquery_manager.get_orders_by_session(session_id)
        confirmed_orders_db = [o for o in orders_from_bigquery if o["status"] == "confirmed"]
        
        ordered_cars_session_cache = state.get("ordered_cars", []) 
        
        all_unique_orders = {}
        
        for order in confirmed_orders_db:
            all_unique_orders[order["model"].lower()] = {
                "model": order["model"],
                "price": order["price"],
                "source": "database"
            }
        
        for car in ordered_cars_session_cache:
            if car["model"].lower() not in all_unique_orders:
                 all_unique_orders[car["model"].lower()] = {
                    "model": car["model"],
                    "price": car["price"],
                    "source": "session"
                }
        
        final_orders_list = list(all_unique_orders.values())

        if not final_orders_list:
            logger.info("No confirmed orders found for status inquiry.")
            return {
                "status": "no_orders",
                "message": "You don't have any confirmed orders yet. Would you like to place an order?"
            }
        
        if len(final_orders_list) == 1:
            order = final_orders_list[0]
            price_formatted = f"${order['price']/100:,.0f}"
            logger.info(f"Single confirmed order for status: {order['model']}")
            return {
                "status": "has_orders",
                "message": f"✅ Yes, you have a confirmed order for the {order['model']} ({price_formatted}). It should be ready for pickup at your nearest Ford dealership."
            }
        else:
            sorted_orders = sorted(final_orders_list, key=lambda x: x['model'])
            order_list_formatted = ", ".join([f"{order['model']} (${order['price']/100:,.0f})" for order in sorted_orders])
            logger.info(f"Multiple confirmed orders for status: {len(sorted_orders)} found.")
            return {
                "status": "has_orders", 
                "message": f"✅ You have {len(sorted_orders)} confirmed orders: {order_list_formatted}. All vehicles should be ready for pickup at your nearest Ford dealership."
            }
        
    except Exception as e:
        logger.error(f"Error handling order status: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "I had trouble checking your order status. Please try again."
        }

def _handle_new_order(user_input: str, state: dict, session_id: str, user_name: str) -> dict:
    try:
        if "pending_order" in state:
            logger.info("Clearing existing pending order before new request.")
            state["pending_order"] = None
            state["pending_order_confirmation_phrase"] = None

        model_name = _extract_model_from_input(user_input)
        
        if not model_name:
            logger.info("No valid model name extracted from new order request.")
            return {
                "status": "no_model",
                "message": "I couldn't identify a specific model from your request. Which Ford vehicle are you interested in ordering?"
            }
        
        vehicles = bigquery_manager.search_inventory(model_name, limit=1)
        
        if not vehicles:
            logger.info(f"Model '{model_name}' not found in inventory for new order request.")
            return {
                "status": "not_found",
                "message": f"I couldn't find '{model_name}' in our inventory. Could you please specify which Ford model you're interested in?"
            }
        
        vehicle = vehicles[0]
        
        if vehicle["stock"] <= 0:
            logger.info(f"Model '{vehicle['model']}' is out of stock for order proposal.")
            return {
                "status": "out_of_stock",
                "message": f"Unfortunately, the {vehicle['model']} is currently out of stock. Would you like me to check other similar models?"
            }
        
        state["pending_order"] = {
            "model": vehicle["model"],
            "price": vehicle["price"],
            "delivery_days": vehicle["delivery_days"],
            "stock": vehicle["stock"]
        }
        
        confirmation_phrase = f"Confirm order for {vehicle['model']}"
        state["pending_order_confirmation_phrase"] = confirmation_phrase
        
        price_formatted = f"${vehicle['price']/100:,.0f}"
        
        logger.info(f"Proposed order for {vehicle['model']}. Awaiting specific confirmation phrase: '{confirmation_phrase}'")
        return {
            "status": "awaiting_specific_confirmation",
            "model": vehicle["model"],
            "price": vehicle["price"],
            "delivery_days": vehicle["delivery_days"],
            "message": (
                f"🚗 Great choice! I found the {vehicle['model']} for you.\n\n"
                f"📋 Details:\n"
                f"• Price: {price_formatted}\n"
                f"• Estimated Delivery: {vehicle['delivery_days']} days\n"
                f"• Stock: {vehicle['stock']} units available\n\n"
                f"To finalize this order, please confirm by saying: '{confirmation_phrase}'"
            )
        }
        
    except Exception as e:
        logger.error(f"Error handling new order proposal: {e}", exc_info=True)
        if "pending_order" in state:
                state["pending_order"] = None
                state["pending_order_confirmation_phrase"] = None
        return {
            "status": "error",
            "message": "I had trouble processing your order request. Please try again."
        }

def _handle_unclear_request(user_input: str) -> dict:
    logger.info(f"Unclear request received: '{user_input}'")
    return {
        "status": "unclear",
        "message": "I can help you with ordering vehicles, checking order status, or cancelling orders. What would you like to do?"
    }

def _extract_model_from_input(user_input: str) -> str:
    try:
        all_available_models = bigquery_manager.get_all_available_models()
        unique_models = list(set(all_available_models))
        unique_models_lower = [m.lower() for m in unique_models]
        
        user_input_lower = user_input.lower()
        
        common_prepositions_verbs_articles = ["order", "buy", "purchase", "book", "get", "want", "cancel", "my", "the", "a", "an",
                                              "for", "of", "please", "to", "i", "can", "you", "me", "car", "vehicle", "what"]
        
        cleaned_input_words = [word for word in user_input_lower.split() if word not in common_prepositions_verbs_articles]
        cleaned_input = " ".join(cleaned_input_words).strip()
        
        if not cleaned_input:
            logger.debug(f"No meaningful model extracted after cleaning input: '{user_input}'")
            return ""

        if cleaned_input in unique_models_lower:
            original_case_model = unique_models[unique_models_lower.index(cleaned_input)]
            logger.debug(f"Exact match on cleaned input: '{original_case_model}'")
            return original_case_model
        
        for model in unique_models:
            if model.lower() == user_input_lower:
                logger.debug(f"Direct match on full user input: '{model}'")
                return model
        
        matches = difflib.get_close_matches(cleaned_input, unique_models_lower, n=1, cutoff=0.75)
        if matches:
            original_case_model = unique_models[unique_models_lower.index(matches[0])]
            logger.debug(f"Fuzzy match on cleaned input: '{original_case_model}'")
            return original_case_model
        
        for model in unique_models:
            if model.lower() in user_input_lower:
                logger.debug(f"Substring match: '{model}' found in user input.")
                return model
        
        logger.debug(f"No model found for input: '{user_input}' (cleaned: '{cleaned_input}')")
        return ""
        
    except Exception as e:
        logger.error(f"Error extracting model from input: {e}", exc_info=True)
        return ""
