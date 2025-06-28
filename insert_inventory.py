import sys
sys.path.append('.')

from car_support_agent.database.bigquery_manager import bigquery_manager

print("Inserting default inventory data...")

# Delete existing data first (if any)
try:
    query = f"DELETE FROM `{bigquery_manager.inventory_table_id}` WHERE TRUE"
    job = bigquery_manager.client.query(query)
    job.result()
    print("✓ Cleared existing inventory data")
except Exception as e:
    print(f"Note: {e}")

# Insert default inventory
default_inventory = [
    {"model": "Mustang", "price": 2799500, "stock": 8, "delivery_days": 5, "category": "Sports Car", "fuel_type": "Gas"},
    {"model": "Explorer", "price": 3962500, "stock": 5, "delivery_days": 9, "category": "SUV", "fuel_type": "Gas"},
    {"model": "Explorer EV", "price": 4850000, "stock": 3, "delivery_days": 15, "category": "SUV", "fuel_type": "Electric"},
    {"model": "Maverick", "price": 2699500, "stock": 12, "delivery_days": 5, "category": "Truck", "fuel_type": "Gas"},
    {"model": "F-150", "price": 3519000, "stock": 7, "delivery_days": 8, "category": "Truck", "fuel_type": "Gas"},
    {"model": "F-150 Lightning", "price": 5200000, "stock": 4, "delivery_days": 20, "category": "Truck", "fuel_type": "Electric"},
    {"model": "Bronco", "price": 3749000, "stock": 4, "delivery_days": 12, "category": "SUV", "fuel_type": "Gas"},
    {"model": "Escape", "price": 2520000, "stock": 9, "delivery_days": 6, "category": "SUV", "fuel_type": "Gas"}
]

# Add timestamps as strings
from datetime import datetime
current_time = datetime.utcnow().isoformat()
for item in default_inventory:
    item["created_at"] = current_time
    item["updated_at"] = current_time

# Insert data
table_ref = bigquery_manager.client.dataset(bigquery_manager.dataset_id).table("vehicles")
table = bigquery_manager.client.get_table(table_ref)
errors = bigquery_manager.client.insert_rows_json(table, default_inventory)

if not errors:
    print(f"✓ Inserted {len(default_inventory)} vehicles successfully!")
else:
    print(f"✗ Errors inserting data: {errors}")

# Test the insertion
models = bigquery_manager.get_all_available_models()
print(f"✓ Verification: Found {len(models)} available models")
for model in models:
    print(f"  - {model}")
