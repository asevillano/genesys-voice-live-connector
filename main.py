"""
Genesys Cloud Audio Connector - Voice Agent (Python)

This is a Python implementation for integrating Genesys Cloud AudioConnector 
with Azure Voice Live API.
"""
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

from src.python.services.cosmos_db import init_cosmos_db
from src.python.websocket.server import WebSocketServer

async def main():
    print("Starting Python Voice Agent service.")
    
    # Initialize Cosmos DB connection
    init_cosmos_db()
    
    # Start WebSocket server
    server = WebSocketServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
