#!/usr/bin/env python3
"""
Car Support Agent - Database Setup and Test Script

This script:
1. Tests the database connection
2. Verifies table creation
3. Tests basic operations
4. Validates data integrity

Run this script to ensure your BigQuery setup is working correctly.

Usage:
    python deployment/setup.py
"""

import sys
import os
import logging
from typing import Dict, Any

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Also add current working directory
sys.path.append('.')

try:
    from car_support_agent.config.vertex_ai_config import config
    from car_support_agent.database.bigquery_manager import bigquery_manager
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this from the project root directory")
    print("And that you've installed the requirements: pip install -r requirements.txt")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_configuration():
    """Test that configuration is properly loaded"""
    print("=" * 60)
    print("TESTING CONFIGURATION")
    print("=" * 60)
    
    try:
        print(f"✓ Project ID: {config.project_id}")
        print(f"✓ Location: {config.location}")
        print(f"✓ Dataset: {config.dataset_id}")
        print(f"✓ Inventory Table: {config.inventory_table_full_id}")
        print(f"✓ Orders Table: {config.orders_table_full_id}")
        
        if config.agent_id:
            print(f"✓ Agent ID: {config.agent_id}")
        else:
            print("⚠ Agent ID not set (will be needed after Vertex AI deployment)")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_bigquery_connection():
    """Test BigQuery connection and basic operations"""
    print("\n" + "=" * 60)
    print("TESTING BIGQUERY CONNECTION")
    print("=" * 60)
    
    try:
        if bigquery_manager is None:
            print("✗ BigQuery Manager is None")
            return False
        
        print("✓ BigQuery Manager initialized")
        
        # Test basic query
        models = bigquery_manager.get_all_available_models()
        print(f"✓ Found {len(models)} available models")
        
        if models:
            print("Available models:")
            for model in models[:5]:  # Show first 5
                print(f"  - {model}")
            if len(models) > 5:
                print(f"  ... and {len(models) - 5} more")
        
        return True
        
    except Exception as e:
        print(f"✗ BigQuery connection error: {e}")
        return False

def test_inventory_operations():
    """Test inventory search and operations"""
    print("\n" + "=" * 60)
    print("TESTING INVENTORY OPERATIONS")
    print("=" * 60)
    
    try:
        # Test 1: Search for specific model
        print("Test 1: Searching for 'Mustang'")
        results = bigquery_manager.search_inventory("mustang")
        if results:
            vehicle = results[0]
            print(f"✓ Found: {vehicle['model']} - ${vehicle['price']/100:,.2f} - Stock: {vehicle['stock']}")
        else:
            print("✗ No results for 'Mustang'")
            return False
        
        # Test 2: Get vehicle by exact model
        print("\nTest 2: Get vehicle by exact model")
        vehicle = bigquery_manager.get_vehicle_by_model("Explorer EV")
        if vehicle:
            print(f"✓ Found Explorer EV: ${vehicle['price']/100:,.2f} - Stock: {vehicle['stock']}")
        else:
            print("⚠ Explorer EV not found")
        
        # Test 3: Fuzzy search
        print("\nTest 3: Fuzzy search for 'explore'")
        results = bigquery_manager.search_inventory("explore")
        print(f"✓ Fuzzy search returned {len(results)} results")
        for result in results[:3]:
            print(f"  - {result['model']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Inventory operations error: {e}")
        return False

def test_order_operations():
    """Test order creation and management"""
    print("\n" + "=" * 60)
    print("TESTING ORDER OPERATIONS")
    print("=" * 60)
    
    try:
        # Test 1: Create order
        print("Test 1: Creating test order")
        order = bigquery_manager.create_order(
            model="Mustang",
            user_name="Test User",
            session_id="test_session_123"
        )
        
        if order:
            print(f"✓ Created order: {order['order_id']}")
            print(f"  Model: {order['model']}")
            print(f"  Price: ${order['price']/100:,.2f}")
            print(f"  Status: {order['status']}")
        else:
            print("✗ Failed to create order")
            return False
        
        # Test 2: Get order details
        print("\nTest 2: Retrieving order details")
        retrieved_order = bigquery_manager.get_order(order['order_id'])
        if retrieved_order:
            print(f"✓ Retrieved order: {retrieved_order['order_id']}")
        else:
            print("✗ Failed to retrieve order")
            return False
        
        # Test 3: Get orders by session
        print("\nTest 3: Getting orders by session")
        session_orders = bigquery_manager.get_orders_by_session("test_session_123")
        print(f"✓ Found {len(session_orders)} orders for test session")
        
        # Test 4: Cancel order (cleanup)
        print("\nTest 4: Cancelling test order")
        success = bigquery_manager.cancel_order(order['order_id'])
        if success:
            print("✓ Successfully cancelled test order")
        else:
            print("⚠ Failed to cancel test order")
        
        return True
        
    except Exception as e:
        print(f"✗ Order operations error: {e}")
        return False

def test_data_integrity():
    """Test data integrity and validation"""
    print("\n" + "=" * 60)
    print("TESTING DATA INTEGRITY")
    print("=" * 60)
    
    try:
        # Test 1: Check all vehicles have required fields
        print("Test 1: Checking vehicle data integrity")
        all_models = bigquery_manager.get_all_available_models()
        
        for model in all_models[:5]:  # Check first 5
            vehicle = bigquery_manager.get_vehicle_by_model(model)
            if not vehicle:
                print(f"✗ Could not retrieve details for {model}")
                continue
            
            # Check required fields
            required_fields = ['model', 'price', 'stock', 'delivery_days']
            missing_fields = [field for field in required_fields if field not in vehicle or vehicle[field] is None]
            
            if missing_fields:
                print(f"✗ {model} missing fields: {missing_fields}")
            else:
                print(f"✓ {model} data integrity OK")
        
        # Test 2: Check price format (should be in cents)
        print("\nTest 2: Checking price formats")
        vehicle = bigquery_manager.get_vehicle_by_model("Mustang")
        if vehicle and vehicle['price'] > 100000:  # Should be in cents, so > $1000
            print(f"✓ Price format correct: {vehicle['price']} cents = ${vehicle['price']/100:,.2f}")
        else:
            print("⚠ Price format might be incorrect")
        
        return True
        
    except Exception as e:
        print(f"✗ Data integrity error: {e}")
        return False

def print_summary(results: Dict[str, bool]):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:<30} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your BigQuery setup is working correctly.")
        print("\nNext steps:")
        print("1. Your database is ready")
        print("2. You can now create the agent tools")
        print("3. Deploy to Vertex AI Agent Engine")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Check your .env file configuration")
        print("2. Verify Google Cloud authentication")
        print("3. Ensure BigQuery API is enabled")
        print("4. Check service account permissions")

def main():
    """Run all database tests"""
    print("Car Support Agent - Database Setup and Test")
    print("This will test your BigQuery database setup\n")
    
    # Run all tests
    test_results = {
        "Configuration": test_configuration(),
        "BigQuery Connection": test_bigquery_connection(),
        "Inventory Operations": test_inventory_operations(),
        "Order Operations": test_order_operations(),
        "Data Integrity": test_data_integrity()
    }
    
    # Print summary
    print_summary(test_results)
    
    # Exit with appropriate code
    if all(test_results.values()):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()