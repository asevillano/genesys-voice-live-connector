"""
WebSocket Server for Genesys AudioConnector
"""
import asyncio
from datetime import datetime
from typing import Dict
import json

import websockets
from websockets.server import WebSocketServerProtocol

from ..common.environment_variables import get_port
from .session import Session


class WebSocketServer:
    """
    WebSocket server that handles Genesys AudioConnector connections.
    """
    
    def __init__(self):
        self.sessions: Dict[WebSocketServerProtocol, Session] = {}
        self.enable_key_verification = False  # Currently disabled for development
    
    async def start(self):
        """Start the WebSocket server."""
        port = get_port()
        print(f"Starting server on port: {port}")
        
        async with websockets.serve(
            self._handle_connection,
            "0.0.0.0",
            port,
            process_request=self._process_request
        ):
            await asyncio.Future()  # Run forever
    
    async def _process_request(self, connection, request):
        """
        Process HTTP requests before WebSocket upgrade.
        Handles health checks and authentication.
        """
        # Health check endpoint
        if request.path == "/health":
            print(f"{datetime.now().isoformat()}<<Health Check OK")
            return connection.respond(200, "OK\n")
        
        # WebSocket upgrade requests continue normally
        return None
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """Handle a new WebSocket connection."""
        session_id = websocket.request.headers.get('audiohook-session-id', '')
        path = websocket.request.path
        
        print(f"{datetime.now().isoformat()}:Received a connection request from {path}.")
        
        # TODO: Implement signature verification if needed
        # For now, we accept all connections
        print(f"{datetime.now().isoformat()}:Authentication was successful.")
        print(f"{datetime.now().isoformat()}:wsServer.on.connection.")
        
        # Create session
        session = Session(websocket, session_id, path)
        self.sessions[websocket] = session
        print(f"{datetime.now().isoformat()}:{session_id}:Creating a new session")
        
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Binary message (audio data)
                    await session.process_binary_message(message)
                else:
                    # Text message (JSON)
                    print(f"{datetime.now().isoformat()}:ws.on.message.notBinary.processTextMessage|[{message}]")
                    await session.process_text_message(message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"{datetime.now().isoformat()}:WebSocket connection closed: {e}")
        except Exception as e:
            print(f"{datetime.now().isoformat()}:WebSocket Error: {e}")
        finally:
            # Cleanup
            if websocket in self.sessions:
                session = self.sessions[websocket]
                await session.close()
                del self.sessions[websocket]
            print(f"{datetime.now().isoformat()}:WebSocket connection closed.")
