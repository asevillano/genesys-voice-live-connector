"""
Cosmos DB integration for invoice queries
"""
import os
from typing import Optional, Dict, Any, List
import re

# Cosmos DB container reference
_cosmos_container = None


def init_cosmos_db():
    """Initialize Cosmos DB connection. Should be called once at startup."""
    global _cosmos_container
    
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    database_name = os.getenv("COSMOS_DATABASE_NAME")
    container_name = os.getenv("COSMOS_CONTAINER_NAME")
    
    if endpoint and key and database_name and container_name:
        try:
            from azure.cosmos import CosmosClient
            
            client = CosmosClient(endpoint, key)
            database = client.get_database_client(database_name)
            _cosmos_container = database.get_container_client(container_name)
            print(f"[CosmosDB] Connected to database '{database_name}', container '{container_name}'")
        except Exception as e:
            print(f"[CosmosDB] Failed to initialize: {e}")
    else:
        print("[CosmosDB] Missing configuration. Set COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DATABASE_NAME, COSMOS_CONTAINER_NAME")


async def get_invoices(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get billing/invoice information from Cosmos DB.
    
    Args:
        args: Dictionary containing accountId (DNI) to search for
        
    Returns:
        Invoice data from Cosmos DB
    """
    account_id = args.get('accountId')
    
    print(f"[getInvoices] Raw account_id: {account_id}")
    
    # Extract 8-9 digits followed by a letter (DNI format)
    if account_id:
        match = re.search(r'(\d{8,9}[A-Za-z])', account_id)
        if match:
            account_id = match.group(1)
        else:
            account_id = None
    
    print(f"[getInvoices] Processed account_id: {account_id}")
    
    if _cosmos_container is None:
        print("[getInvoices] Cosmos DB not initialized")
        return {
            'status': 'error',
            'account_id': account_id,
            'invoices': [],
            'total_invoices': 0,
            'error': 'Database connection not available'
        }
    
    try:
        # Build query with parameterized parameters to prevent SQL injection
        if account_id:
            query = "SELECT * FROM c WHERE c.TitularDNI = @accountId"
            parameters = [{"name": "@accountId", "value": account_id}]
        else:
            query = "SELECT * FROM c"
            parameters = None
        
        print(f"[getInvoices] Executing query: {query} with params: {parameters}")
        
        # Execute query
        query_kwargs = {
            "query": query,
            "enable_cross_partition_query": True
        }
        if parameters:
            query_kwargs["parameters"] = parameters
        
        items = list(_cosmos_container.query_items(**query_kwargs))
        
        print(f"[getInvoices] Found {len(items)} invoices")
        
        return {
            'status': 'success',
            'account_id': account_id,
            'invoices': items,
            'total_invoices': len(items)
        }
    except Exception as e:
        error_message = str(e)
        print(f"[getInvoices] Error querying Cosmos DB: {error_message}")
        return {
            'status': 'error',
            'account_id': account_id,
            'invoices': [],
            'total_invoices': 0,
            'error': error_message
        }
