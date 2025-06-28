# 🚗 Ford Car Support Agent

An intelligent AI-powered customer support agent for Ford vehicle inquiries, built with Google Agent Development Kit (ADK) and deployed on Vertex AI Agent Engine.

## 🌟 Features

- **🔍 Vehicle Specifications**: Detailed technical information about Ford vehicles using web search
- **📋 Inventory Management**: Real-time availability, pricing, and stock levels via BigQuery
- **🛒 Order Processing**: Complete order lifecycle from placement to cancellation
- **🤖 Multi-Agent Architecture**: Specialized sub-agents for different customer needs
- **☁️ Cloud Deployment**: Scalable deployment on Google Cloud Platform



### Agent Hierarchy

**🎯 Main Coordinator Agent**
- Routes customer queries to specialized agents
- Manages conversation flow and context
- Provides cohesive customer experience

**📊 Sub-Agents**
- **Inventory Agent**: Vehicle availability, pricing, stock levels
- **Order Agent**: Order placement, confirmation, cancellation, status
- **Car Specs Agent**: Technical specifications via web search

## 🚀 Quick Start

### Prerequisites

- Python 3.8-3.12
- Google Cloud Platform account
- Vertex AI API enabled
- BigQuery dataset configured

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ford-car-support-agent.git
   cd ford-car-support-agent
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Environment Configuration

Create a `.env` file with the following variables:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CLOUD_STORAGE_BUCKET=your-staging-bucket

# Vertex AI Configuration
VERTEX_AI_MODEL=gemini-1.5-pro
VERTEX_AI_AGENT_ID=your-agent-id-after-deployment

# BigQuery Configuration
BIGQUERY_DATASET_ID=car_inventory
INVENTORY_TABLE_ID=vehicles
ORDERS_TABLE_ID=customer_orders

# Environment Settings
ENVIRONMENT=local
LOG_LEVEL=INFO
```
**Authenticate with Google Cloud**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

## ☁️ Cloud Deployment

### Deploy to Vertex AI Agent Engine

 **Deploy the agent**
   ```bash
   python -m car_support_agent.deployment.deploy --create
   ```

 **Update environment with Agent ID**
   ```bash
   # Add the returned agent ID to your .env file
   VERTEX_AI_AGENT_ID=your-deployed-agent-id
   ```
 **Test the deployed agent**
   ```bash
   python test_deployed_agent.py
   ```

### Deployment Management

```bash
# List deployed agents
python -m car_support_agent.deployment.deploy --list


# Delete agent
python -m car_support_agent.deployment.deploy --delete --resource_id=AGENT_ID
```

## 💬 Usage Examples

### Customer Interactions

**Vehicle Specifications**
```
Customer: "Tell me about Mustang specs"
Agent: 🚗 2025 Ford Mustang Specifications:
       • GT: 5.0L V8, 450 HP, 410 lb-ft torque
       • EcoBoost: 2.3L Turbo I4, 310 HP, 350 lb-ft torque
       [detailed specifications...]
```

**Inventory Check**
```
Customer: "Is Bronco available?"
Agent: "Yes, we have the Bronco in stock! We currently have 2 units available at $37,490."
```

**Order Placement**
```
Customer: "I want to order a Mustang"
Agent: 🚗 Great choice! Found the Mustang for you.
       Price: $27,995 | Delivery: 5 days | Stock: 4 units
       Would you like to proceed with booking?

Customer: "Yes"
Agent: ✅ Excellent! Your Mustang has been reserved!
       Order ID: ABC123 | Estimated Delivery: 5 days
```


### Key Components

- **agent.py**: Main coordinator with sub-agent orchestration
- **Tools**: Custom tools for inventory search and order processing
- **BigQuery Manager**: Database operations and query handling
- **Sub-agents**: Specialized agents for inventory, orders, and specifications
- **Deployment**: Scripts for cloud deployment and management
- **Frontend**: React-based user interface (ford-support-frontend)

