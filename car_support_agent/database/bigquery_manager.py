
"""
BigQuery Manager for Car Support Agent

This module handles all BigQuery operations:
1. Database setup (datasets, tables, schemas)
2. Inventory management (search, update stock)
3. Order management (create, track, cancel orders)
4. Data validation and error handling

Why BigQuery over JSON files:
- Concurrent access (multiple users simultaneously)
- ACID transactions (data integrity)
- SQL-based queries (powerful search capabilities)
- Scalability (handles large datasets)
- Analytics capabilities (reports, insights)
"""

from google.cloud import bigquery
from google.auth import exceptions as auth_exceptions
from google.api_core.exceptions import Conflict, NotFound # Import Conflict and NotFound
from car_support_agent.config.vertex_ai_config import config
from typing import Dict, List, Any, Optional, Union
import logging
import uuid
from datetime import datetime
import difflib

logger = logging.getLogger(__name__)

class BigQueryManager:
    """
    Manages all BigQuery operations for the car support agent
    
    This class provides:
    1. Automatic database setup
    2. Inventory operations (search, stock management)
    3. Order operations (create, track, cancel)
    4. Data validation and error handling
    """
    
    def __init__(self):
        """Initialize BigQuery client and setup database"""
        try:
            # Initialize BigQuery client
            self.client = bigquery.Client(project=config.project_id)
            self.dataset_id = config.dataset_id
            self.inventory_table_id = config.inventory_table_full_id
            self.orders_table_id = config.orders_table_full_id
            
            logger.info(f"BigQuery Manager initialized for project: {config.project_id}")
            
            # Setup database structure
            self._setup_database()
            
            logger.info("BigQuery Manager ready")
            
        except auth_exceptions.GoogleAuthError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing BigQuery Manager: {e}")
            # In development, we might want to continue without BigQuery, but not if it crashed on prod setup
            if config and config.is_local_development():
                logger.warning("BigQuery Manager failed in development mode but will proceed.")
                # We don't re-raise here for development mode to allow the app to run
            else:
                # In non-development (e.g., deployment), we fail hard if setup fails
                logger.error("Failed to initialize BigQuery Manager in non-development mode. Exiting.")
                raise # Re-raise for deployment to highlight critical error
    
    def _setup_database(self):
        """
        Setup BigQuery dataset and tables if they don't exist
        
        This method:
        1. Creates the dataset if missing
        2. Creates inventory table with proper schema
        3. Creates orders table with proper schema
        4. Inserts default inventory data if empty
        """
        try:
            # Create dataset (already handles Conflict internally)
            self._create_dataset()
            
            # Create tables (now idempotent)
            self._create_inventory_table()
            self._create_orders_table()
            
            # Insert default data if inventory is empty
            self._ensure_default_inventory()
            
            logger.info("Database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            raise # Re-raise to be caught by __init__
    
    def _create_dataset(self):
        """Create BigQuery dataset if it doesn't exist"""
        dataset_ref = self.client.dataset(config.dataset_id)
        
        try:
            # Try to get the dataset. If it exists, get_dataset will succeed.
            self.client.get_dataset(dataset_ref)
            logger.info(f"Dataset {config.dataset_id} already exists. Reusing it.")
        except NotFound:
            # Dataset does not exist, so create it
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = config.location
            dataset.description = "Car inventory and order management data"
            
            try:
                dataset = self.client.create_dataset(dataset, timeout=30)
                logger.info(f"Created dataset: {config.dataset_id} at {dataset.location}")
            except Conflict:
                # Handle the race condition: it was created by another process
                # between the get_dataset call and this create_dataset call.
                logger.info(f"Dataset {config.dataset_id} was just created by another process. Reusing it.")
            except Exception as e:
                # Catch any other unexpected errors during dataset creation and re-raise
                logger.error(f"Error creating dataset {config.dataset_id}: {e}")
                raise
        except Exception as e:
            # This catches unexpected errors while trying to get the dataset, but not NotFound or Conflict
            logger.error(f"Error checking existence of dataset {config.dataset_id}: {e}")
            raise
    
    def _create_inventory_table(self):
        """Create inventory table with proper schema"""
        table_ref = self.client.dataset(config.dataset_id).table(config.inventory_table_id)
        
        try:
            self.client.get_table(table_ref)
            logger.info(f"Inventory table '{config.inventory_table_full_id}' already exists. Reusing it.")
            return # Table exists, nothing more to do
        except NotFound:
            # Table doesn't exist, proceed to create it
            logger.info(f"Inventory table '{config.inventory_table_full_id}' not found. Creating it.")
        except Exception as e:
            # Catch other unexpected errors during get_table
            logger.error(f"Error checking existence of inventory table '{config.inventory_table_full_id}': {e}")
            raise # Re-raise to propagate the error

        # Define inventory table schema
        schema = [
            bigquery.SchemaField("model", "STRING", mode="REQUIRED", 
                                description="Car model name (e.g., 'Mustang', 'Explorer EV')"),
            bigquery.SchemaField("price", "INTEGER", mode="REQUIRED", 
                                description="Price in USD cents (e.g., 2799500 = $27,995)"),
            bigquery.SchemaField("stock", "INTEGER", mode="REQUIRED", 
                                description="Number of vehicles available"),
            bigquery.SchemaField("delivery_days", "INTEGER", mode="REQUIRED", 
                                description="Estimated delivery time in days"),
            bigquery.SchemaField("category", "STRING", mode="NULLABLE", 
                                description="Vehicle category (SUV, Truck, etc.)"),
            bigquery.SchemaField("fuel_type", "STRING", mode="NULLABLE", 
                                description="Fuel type (Gas, Electric, Hybrid)"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", 
                                description="When this record was created"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED", 
                                description="When this record was last updated"),
        ]
        
        table = bigquery.Table(table_ref, schema=schema)
        table.description = "Vehicle inventory with pricing and availability"
        
        try:
            table = self.client.create_table(table)
            logger.info(f"Created inventory table: {table.table_id}")
        except Conflict:
            # Handle the race condition: table was just created by another process
            logger.info(f"Inventory table '{config.inventory_table_full_id}' was just created by another process. Reusing it.")
        except Exception as e:
            # Catch any other unexpected errors during table creation
            logger.error(f"Error creating inventory table '{config.inventory_table_full_id}': {e}")
            raise # Re-raise to propagate the error
    
    def _create_orders_table(self):
        """Create orders table with proper schema"""
        table_ref = self.client.dataset(config.dataset_id).table(config.orders_table_id)
        
        try:
            self.client.get_table(table_ref)
            logger.info(f"Orders table '{config.orders_table_full_id}' already exists. Reusing it.")
            return # Table exists, nothing more to do
        except NotFound:
            # Table doesn't exist, proceed to create it
            logger.info(f"Orders table '{config.orders_table_full_id}' not found. Creating it.")
        except Exception as e:
            # Catch other unexpected errors during get_table
            logger.error(f"Error checking existence of orders table '{config.orders_table_full_id}': {e}")
            raise # Re-raise to propagate the error
        
        # Define orders table schema
        schema = [
            bigquery.SchemaField("order_id", "STRING", mode="REQUIRED", 
                                description="Unique order identifier"),
            bigquery.SchemaField("session_id", "STRING", mode="NULLABLE", 
                                description="Conversation session ID"),
            bigquery.SchemaField("user_name", "STRING", mode="NULLABLE", 
                                description="Customer name"),
            bigquery.SchemaField("model", "STRING", mode="REQUIRED", 
                                description="Ordered vehicle model"),
            bigquery.SchemaField("price", "INTEGER", mode="REQUIRED", 
                                description="Order price in USD cents"),
            bigquery.SchemaField("delivery_days", "INTEGER", mode="REQUIRED", 
                                description="Estimated delivery time"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED", 
                                description="Order status: pending, confirmed, cancelled"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", 
                                description="When order was created"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED", 
                                description="When order was last updated"),
        ]
        
        table = bigquery.Table(table_ref, schema=schema)
        table.description = "Customer orders with status tracking"
        
        try:
            table = self.client.create_table(table)
            logger.info(f"Created orders table: {table.table_id}")
        except Conflict:
            # Handle the race condition: table was just created by another process
            logger.info(f"Orders table '{config.orders_table_full_id}' was just created by another process. Reusing it.")
        except Exception as e:
            # Catch any other unexpected errors during table creation
            logger.error(f"Error creating orders table '{config.orders_table_full_id}': {e}")
            raise # Re-raise to propagate the error
    
    def _ensure_default_inventory(self):
        """Insert default inventory data if table is empty"""
        try:
            # Check if inventory table has data
            # Use full table ID in query
            query = f"SELECT COUNT(*) as count FROM `{self.inventory_table_id}`"
            query_job = self.client.query(query)
            result = list(query_job.result())[0]
            
            if result.count > 0:
                logger.info(f"Inventory table has {result.count} vehicles")
                return
            
            # Table is empty, insert default data
            logger.info("Inventory table is empty. Inserting default data.")
            self._insert_default_inventory()
            
        except Exception as e:
            logger.error(f"Error checking/inserting default inventory: {e}")
            # Depending on desired behavior, you might want to re-raise here for critical failures.
            # For now, it will just log the error and proceed with an empty inventory.
    
    def _insert_default_inventory(self):
        """Insert default car inventory data"""
        default_inventory = [
            {
                "model": "Mustang",
                "price": 2799500,  # $27,995 in cents
                "stock": 8,
                "delivery_days": 5,
                "category": "Sports Car",
                "fuel_type": "Gas"
            },
            {
                "model": "Explorer",
                "price": 3962500,  # $39,625 in cents
                "stock": 5,
                "delivery_days": 9,
                "category": "SUV",
                "fuel_type": "Gas"
            },
            {
                "model": "Explorer EV",
                "price": 4850000,  # $48,500 in cents
                "stock": 3,
                "delivery_days": 15,
                "category": "SUV",
                "fuel_type": "Electric"
            },
            {
                "model": "Maverick",
                "price": 2699500,  # $26,995 in cents
                "stock": 12,
                "delivery_days": 5,
                "category": "Truck",
                "fuel_type": "Gas"
            },
            {
                "model": "F-150",
                "price": 3519000,  # $35,190 in cents
                "stock": 7,
                "delivery_days": 8,
                "category": "Truck",
                "fuel_type": "Gas"
            },
            {
                "model": "F-150 Lightning",
                "price": 5200000,  # $52,000 in cents
                "stock": 4,
                "delivery_days": 20,
                "category": "Truck",
                "fuel_type": "Electric"
            },
            {
                "model": "Bronco",
                "price": 3749000,  # $37,490 in cents
                "stock": 4,
                "delivery_days": 12,
                "category": "SUV",
                "fuel_type": "Gas"
            },
            {
                "model": "Escape",
                "price": 2520000,  # $25,200 in cents
                "stock": 9,
                "delivery_days": 6,
                "category": "SUV",
                "fuel_type": "Gas"
            }
        ]
        
        # Add timestamps
        current_time = datetime.utcnow().isoformat() + "Z" # BigQuery expects 'Z' for UTC
        for item in default_inventory:
            item["created_at"] = current_time
            item["updated_at"] = current_time
        
        # Insert data
        table_ref = self.client.dataset(config.dataset_id).table(config.inventory_table_id)
        table = self.client.get_table(table_ref) # Make sure to get the full table object again
        errors = self.client.insert_rows_json(table, default_inventory)
        
        if not errors:
            logger.info(f"Inserted {len(default_inventory)} default inventory items")
        else:
            logger.error(f"Error inserting default data: {errors}")
            # Convert errors to a readable string for the exception
            error_details = ", ".join([str(error) for error in errors])
            raise Exception(f"Failed to insert default inventory: {error_details}")
    
    # ===================================================================
    # INVENTORY OPERATIONS
    # ===================================================================
    
    def search_inventory(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search inventory using flexible SQL queries
        
        Args:
            search_term: User's search input (e.g., "mustang", "explorer ev")
            limit: Maximum number of results to return
            
        Returns:
            List of matching vehicles with details
        """
        try:
            # Clean search term
            search_term = search_term.strip().lower()
            
            if not search_term:
                return []
            
            # Multi-strategy search query
            # Ensure table ID in query uses backticks for full path
            query = f"""
            WITH search_results AS (
                SELECT 
                    model,
                    price,
                    stock,
                    delivery_days,
                    category,
                    fuel_type,
                    -- Ranking based on match quality
                    CASE 
                        WHEN LOWER(model) = @search_term THEN 1
                        WHEN LOWER(model) LIKE CONCAT(@search_term, '%') THEN 2
                        WHEN LOWER(model) LIKE CONCAT('%', @search_term, '%') THEN 3
                        WHEN REGEXP_CONTAINS(LOWER(model), @search_pattern) THEN 4
                        ELSE 5
                    END as match_rank
                FROM `{self.inventory_table_id}`
                WHERE 
                    LOWER(model) LIKE CONCAT('%', @search_term, '%')
                    OR REGEXP_CONTAINS(LOWER(model), @search_pattern)
            )
            SELECT *
            FROM search_results
            ORDER BY match_rank, stock DESC, model
            LIMIT @limit
            """
            
            # Create regex pattern for word matching
            words = search_term.split()
            search_pattern = '|'.join(words) if words else search_term
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("search_term", "STRING", search_term),
                    bigquery.ScalarQueryParameter("search_pattern", "STRING", search_pattern),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            vehicles = []
            for row in results:
                vehicles.append({
                    "model": row.model,
                    "price": row.price,
                    "stock": row.stock,
                    "delivery_days": row.delivery_days,
                    "category": row.category,
                    "fuel_type": row.fuel_type
                })
            
            logger.info(f"Found {len(vehicles)} vehicles for search: '{search_term}'")
            return vehicles
            
        except Exception as e:
            logger.error(f"Error searching inventory: {e}")
            return []
    
    def get_vehicle_by_model(self, model: str) -> Optional[Dict[str, Any]]:
        """
        Get vehicle by exact model name
        
        Args:
            model: Exact model name (case-insensitive)
            
        Returns:
            Vehicle details or None if not found
        """
        try:
            # Ensure table ID in query uses backticks for full path
            query = f"""
            SELECT model, price, stock, delivery_days, category, fuel_type
            FROM `{self.inventory_table_id}`
            WHERE LOWER(model) = LOWER(@model)
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("model", "STRING", model)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                return {
                    "model": row.model,
                    "price": row.price,
                    "stock": row.stock,
                    "delivery_days": row.delivery_days,
                    "category": row.category,
                    "fuel_type": row.fuel_type
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting vehicle by model '{model}': {e}")
            return None
    
    def update_stock(self, model: str, quantity_change: int) -> bool:
        """
        Update vehicle stock (add or subtract)
        
        Args:
            model: Vehicle model name
            quantity_change: Positive to add stock, negative to subtract
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure table ID in query uses backticks for full path
            query = f"""
            UPDATE `{self.inventory_table_id}`
            SET 
                stock = GREATEST(0, stock + @quantity_change),
                updated_at = CURRENT_TIMESTAMP()
            WHERE LOWER(model) = LOWER(@model)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("model", "STRING", model),
                    bigquery.ScalarQueryParameter("quantity_change", "INT64", quantity_change)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            logger.info(f"Updated stock for {model}: {quantity_change:+d}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating stock for {model}: {e}")
            return False
    
    def get_all_available_models(self) -> List[str]:
        """Get all vehicle models that are in stock"""
        try:
            # Ensure table ID in query uses backticks for full path
            query = f"""
            SELECT model
            FROM `{self.inventory_table_id}`
            WHERE stock > 0
            ORDER BY model
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            return [row.model for row in results]
            
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return []
    
    # ===================================================================
    # ORDER OPERATIONS
    # ===================================================================
    
    def create_order(self, model: str, user_name: str = None, session_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Create a new order
        
        Args:
            model: Vehicle model to order
            user_name: Customer name (optional)
            session_id: Conversation session ID (optional)
            
        Returns:
            Order details or None if failed
        """
        try:
            # Get vehicle details
            vehicle = self.get_vehicle_by_model(model)
            if not vehicle:
                logger.error(f"Cannot create order: Vehicle '{model}' not found")
                return None
            
            if vehicle["stock"] <= 0:
                logger.error(f"Cannot create order: '{model}' is out of stock")
                return None
            
            # Create order
            order_id = str(uuid.uuid4())
            current_time = datetime.utcnow().isoformat() + "Z" # Append 'Z' for BigQuery UTC timestamp
            
            order_data = [{
                "order_id": order_id,
                "session_id": session_id,
                "user_name": user_name,
                "model": vehicle["model"],
                "price": vehicle["price"],
                "delivery_days": vehicle["delivery_days"],
                "status": "confirmed",  # Create as confirmed directly
                "created_at": current_time,
                "updated_at": current_time
            }]
            
            # Insert order
            table_ref = self.client.dataset(config.dataset_id).table(config.orders_table_id)
            table = self.client.get_table(table_ref) # Get the full table object again
            errors = self.client.insert_rows_json(table, order_data)
            
            if errors:
                logger.error(f"Error creating order: {errors}")
                return None
            
            logger.info(f"Created order {order_id} for {model}")
            return order_data[0]
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None
    
    def confirm_order(self, order_id: str) -> bool:
        """
        Confirm an order and update stock
        
        Args:
            order_id: Order ID to confirm
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get order details
            order = self.get_order(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False
            
            if order["status"] != "pending":
                logger.error(f"Order {order_id} is not pending (status: {order['status']})")
                return False
            
            # Start transaction-like operation
            # Update order status
            # Ensure table ID in query uses backticks for full path
            update_order_query = f"""
            UPDATE `{self.orders_table_id}`
            SET 
                status = 'confirmed',
                updated_at = CURRENT_TIMESTAMP()
            WHERE order_id = @order_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("order_id", "STRING", order_id)
                ]
            )
            
            query_job = self.client.query(update_order_query, job_config=job_config)
            query_job.result()
            
            # Update inventory stock
            success = self.update_stock(order["model"], -1)
            
            if success:
                logger.info(f"Confirmed order {order_id}")
                return True
            else:
                logger.error(f"Failed to update stock for order {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error confirming order {order_id}: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order and restore stock if it was confirmed
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get order details
            order = self.get_order(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False
            
            if order["status"] == "cancelled":
                logger.info(f"Order {order_id} is already cancelled")
                return True
            
            # Update order status
            # Ensure table ID in query uses backticks for full path
            query = f"""
            UPDATE `{self.orders_table_id}`
            SET 
                status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP()
            WHERE order_id = @order_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("order_id", "STRING", order_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()
            
            # If order was confirmed, restore stock
            if order["status"] == "confirmed":
                self.update_stock(order["model"], 1)
            
            logger.info(f"Cancelled order {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details by ID
        
        Args:
            order_id: Order ID to lookup
            
        Returns:
            Order details or None if not found
        """
        try:
            # Ensure table ID in query uses backticks for full path
            query = f"""
            SELECT *
            FROM `{self.orders_table_id}`
            WHERE order_id = @order_id
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("order_id", "STRING", order_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                return {
                    "order_id": row.order_id,
                    "session_id": row.session_id,
                    "user_name": row.user_name,
                    "model": row.model,
                    "price": row.price,
                    "delivery_days": row.delivery_days,
                    "status": row.status,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    def get_orders_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a session
        
        Args:
            session_id: Session ID to lookup
            
        Returns:
            List of orders for the session
        """
        try:
            # Ensure table ID in query uses backticks for full path
            query = f"""
            SELECT *
            FROM `{self.orders_table_id}`
            WHERE session_id = @session_id
            ORDER BY created_at DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            orders = []
            for row in results:
                orders.append({
                    "order_id": row.order_id,
                    "session_id": row.session_id,
                    "user_name": row.user_name,
                    "model": row.model,
                    "price": row.price,
                    "delivery_days": row.delivery_days,
                    "status": row.status,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders for session {session_id}: {e}")
            return []

# ===================================================================
# GLOBAL INSTANCE
# ===================================================================
# Create a global instance that can be imported throughout the project
# Usage: from car_support_agent.database.bigquery_manager import bigquery_manager

try:
    bigquery_manager = BigQueryManager()
    logger.info("BigQuery Manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize BigQuery Manager: {e}")
    # In development, we might want to continue without BigQuery
    if config and config.is_local_development():
        logger.warning("BigQuery Manager failed in development mode")
        bigquery_manager = None # Assign None so the rest of the app doesn't crash on import
    else:
        # In non-development (e.g., deployment), we fail hard if setup fails
        # The __init__ method should handle this, but adding here as a fallback
        logger.error("Failed to initialize BigQuery Manager. This is a critical error.")
        raise
