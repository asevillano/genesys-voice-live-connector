"""
Message Handler Interface and Registry
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..session import Session


class MessageHandler(ABC):
    """Base class for message handlers."""
    
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        """Handle a message from the client."""
        pass


class OpenMessageHandler(MessageHandler):
    """Handler for 'open' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        from datetime import datetime
        import os
        
        params = message.get('parameters', {})
        
        if not params:
            print("Invalid request parameters.")
            session.send_disconnect('error', 'Invalid request parameters.', {})
            return
        
        session.set_conversation_id(params.get('conversationId', ''))
        
        print("Received an Open Message.")
        
        # Find supported media type (PCMU at 8000Hz)
        selected_media = None
        for media in params.get('media', []):
            if media.get('format') == 'PCMU' and media.get('rate') == 8000:
                selected_media = media
                break
        
        if not selected_media:
            print("No supported media type was found.")
            session.send_disconnect('error', 'No supported media type was found.', {})
            return
        
        print(f"Using MediaParameter {selected_media}")
        session.set_selected_media(selected_media)
        
        if params.get('inputVariables'):
            print(f"Setting input variables: {params['inputVariables']}")
            session.set_input_variables(params['inputVariables'])
        
        # Create voice AI agent now that we have inputVariables
        from ..services.voice_agent_factory import VoiceAIAgentFactory
        BOT_PROVIDER = os.getenv('BOT_PROVIDER', 'voicelive')
        session.voice_ai_agent = VoiceAIAgentFactory.create(BOT_PROVIDER, session)
        
        # Send opened response
        response = session.create_message('opened', {'media': [selected_media]})
        await session.send(response)


class CloseMessageHandler(MessageHandler):
    """Handler for 'close' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        print("Received Close message - sending closed response.")
        session.send_closed()


class PingMessageHandler(MessageHandler):
    """Handler for 'ping' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        session.send_keep_alive()


class PlaybackStartedMessageHandler(MessageHandler):
    """Handler for 'playback_started' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        print("Playback started.")
        session.set_is_audio_playing(True)


class PlaybackCompletedMessageHandler(MessageHandler):
    """Handler for 'playback_completed' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        print("Playback completed.")
        session.playback_completed()


class DTMFMessageHandler(MessageHandler):
    """Handler for 'dtmf' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        params = message.get('parameters', {})
        digit = params.get('digit', '')
        print(f"Received DTMF digit: {digit}")
        session.process_dtmf(digit)


class ErrorMessageHandler(MessageHandler):
    """Handler for 'error' messages."""
    
    async def handle_message(self, message: Dict[str, Any], session: 'Session') -> None:
        params = message.get('parameters', {})
        print(f"Received error: {params.get('message', 'Unknown error')}")


class MessageHandlerRegistry:
    """Registry of message handlers."""
    
    def __init__(self):
        self._handlers: Dict[str, MessageHandler] = {
            'open': OpenMessageHandler(),
            'close': CloseMessageHandler(),
            'ping': PingMessageHandler(),
            'playback_started': PlaybackStartedMessageHandler(),
            'playback_completed': PlaybackCompletedMessageHandler(),
            'dtmf': DTMFMessageHandler(),
            'error': ErrorMessageHandler(),
        }
    
    def get_handler(self, message_type: str) -> MessageHandler:
        """Get the handler for a message type."""
        return self._handlers.get(message_type)
