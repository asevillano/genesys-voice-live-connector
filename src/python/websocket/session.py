"""
WebSocket Session - Manages a single AudioConnector session
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from ..protocol.types import (
    MediaParameter,
    ServerMessage,
    BargeInEvent,
    BotTurnResponseEvent,
    TranscriptEvent,
    TranscriptData
)
from ..common.environment_variables import (
    get_max_binary_message_size,
    get_min_binary_message_size
)
from .audio_pacer import AudioPacedSender
from .message_handlers import MessageHandlerRegistry

import os
BOT_PROVIDER = os.getenv('BOT_PROVIDER', 'voicelive')


class Session:
    """
    Manages a WebSocket session with the Genesys AudioConnector.
    """
    
    def __init__(self, ws, session_id: str, url: str):
        self.ws = ws
        self.client_session_id = session_id
        self.url = url
        
        self.max_binary_message_size = get_max_binary_message_size()
        self.min_binary_message_size = get_min_binary_message_size()
        
        self._disconnecting = False
        self._closed = False
        
        self.message_handler_registry = MessageHandlerRegistry()
        
        self.voice_ai_agent = None
        self.conversation_id: Optional[str] = None
        self.last_server_seq = 0
        self.last_client_seq = 0
        self.input_variables: Dict[str, str] = {}
        self.selected_media: Optional[MediaParameter] = None
        
        self._is_capturing_dtmf = False
        self._is_audio_playing = False
        self._buffer: List[bytes] = []
        self._paced: Optional[AudioPacedSender] = None
        
        print(f"{datetime.now().isoformat()}:[Session]Created a new Session with ID: {self.client_session_id}")
        
        # Voice AI agent will be created when we receive the 'open' message with inputVariables
        self.voice_ai_agent = None
        
        # Will be initialized when we have a WebSocket
        self._paced = AudioPacedSender(ws, 8000, 2, 2, 250)
    
    def get_client_session_id(self) -> str:
        return self.client_session_id
    
    def get_is_audio_playing(self) -> bool:
        return self._is_audio_playing
    
    def set_is_audio_playing(self, value: bool):
        self._is_audio_playing = value
        print(f"{datetime.now().isoformat()}:[Session] isAudioPlaying set to: {value}")
    
    def get_input_variables(self) -> Dict[str, str]:
        return self.input_variables
    
    def set_input_variables(self, variables: Dict[str, str]):
        self.input_variables = variables
        print(f"{datetime.now().isoformat()}:[Session] Input variables set: {json.dumps(variables)}")
    
    def set_conversation_id(self, conversation_id: str):
        self.conversation_id = conversation_id
        print(f"{datetime.now().isoformat()}:[Session] Conversation ID set: {conversation_id}")
    
    def set_selected_media(self, media: MediaParameter):
        self.selected_media = media
        print(f"{datetime.now().isoformat()}:[Session] Selected media set: {json.dumps(media)}")
    
    async def close(self):
        """Close the session."""
        if self._closed:
            print(f"{datetime.now().isoformat()}:[Session] WebSocket connection already Closed")
            return
        
        try:
            print(f"{datetime.now().isoformat()}:[Session]Closing the WebSocket connection.")
            if self.voice_ai_agent:
                await self.voice_ai_agent.close()
            await self.ws.close()
        except Exception as e:
            print(f"{datetime.now().isoformat()}:[Session] Error while closing WebSocket: {e}")
        
        self._closed = True
        print(f"{datetime.now().isoformat()}:[Session] Session marked as closed.")
    
    def playback_completed(self):
        """Called when audio playback is completed."""
        print(f"{datetime.now().isoformat()}:[Session]Playback Completed")
        self.set_is_audio_playing(False)
        if self.voice_ai_agent:
            asyncio.create_task(self.voice_ai_agent.process_playback_completed())
    
    async def process_text_message(self, data: str):
        """Process an incoming text message."""
        if self._closed:
            print(f"{datetime.now().isoformat()}:[Session] Ignoring text message: session is closed.")
            return
        
        message = json.loads(data)
        
        if message.get('type') == 'error' and message.get('parameters'):
            print(f"{datetime.now().isoformat()}:[Session]Received Error Message")
        
        # Validate sequence numbers
        if message.get('seq') != self.last_client_seq + 1:
            print(f"{datetime.now().isoformat()}:[Session]Invalid client sequence number: {message.get('seq')}.")
            self.send_disconnect('error', 'Invalid client sequence number.', {})
            return
        
        self.last_client_seq = message['seq']
        
        if message.get('serverseq', 0) > self.last_server_seq:
            print(f"{datetime.now().isoformat()}:[Session]Invalid server sequence number: {message.get('serverseq')}.")
            self.send_disconnect('error', 'Invalid server sequence number.', {})
            return
        
        if message.get('id') != self.client_session_id:
            print(f"{datetime.now().isoformat()}:Invalid Client Session ID: {message.get('id')}.")
            self.send_disconnect('error', 'Invalid ID specified.', {})
            return
        
        print(f"{datetime.now().isoformat()}:Received a message of type '{message.get('type')}' with parameters: {json.dumps(message.get('parameters', {}))}")
        
        handler = self.message_handler_registry.get_handler(message['type'])
        if not handler:
            print(f"{datetime.now().isoformat()}:Cannot find a message handler for '{message.get('type')}'.")
            return
        
        await handler.handle_message(message, self)
    
    def create_message(self, msg_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a server message."""
        self.last_server_seq += 1
        return {
            'id': self.client_session_id,
            'version': '2',
            'seq': self.last_server_seq,
            'clientseq': self.last_client_seq,
            'type': msg_type,
            'parameters': parameters
        }
    
    async def send(self, message: Dict[str, Any]):
        """Send a message to the client."""
        if message.get('type') == 'event':
            entities = message.get('parameters', {}).get('entities', [])
            entity_type = entities[0].get('type') if entities else 'unknown'
            print(f"{datetime.now().isoformat()}:Sending an {message['type']} message: {entity_type}.")
        else:
            print(f"{datetime.now().isoformat()}:Sending a {message['type']} message.")
        
        await self.ws.send(json.dumps(message))
    
    def flush_buffer(self):
        """Flush the audio buffer."""
        total_length = sum(len(b) for b in self._buffer)
        if total_length <= 0:
            print(f"{datetime.now().isoformat()}:[Session] flushBuffer called but buffer is empty.")
            return
        
        # Combine all buffers
        combined = bytearray(total_length)
        offset = 0
        for buf in self._buffer:
            combined[offset:offset + len(buf)] = buf
            offset += len(buf)
        self._buffer.clear()
        
        data = bytes(combined)
        
        if len(data) <= self.max_binary_message_size:
            print(f"{datetime.now().isoformat()}:[Session] Sending {len(data)} binary bytes in 1 message.")
            asyncio.create_task(self.ws.send(data))
        else:
            pos = 0
            while pos < len(data):
                chunk = data[pos:pos + self.max_binary_message_size]
                print(f"{datetime.now().isoformat()}:[Session] Sending {len(chunk)} binary bytes in chunked message.")
                asyncio.create_task(self.ws.send(chunk))
                pos += self.max_binary_message_size
    
    def send_audio(self, audio_bytes: bytes):
        """Send audio data to the client (paced)."""
        if self._paced:
            self._paced.enqueue(audio_bytes)
    
    def send_barge_in(self):
        """Send a barge-in event."""
        barge_in_event: BargeInEvent = {
            'type': 'barge_in',
            'data': {}
        }
        message = self.create_message('event', {'entities': [barge_in_event]})
        self._buffer.clear()
        if self._paced:
            self._paced.flush_all()
        print(f"{datetime.now().isoformat()}:[Session] Sending barge-in event.")
        asyncio.create_task(self.send(message))
    
    def send_turn_response(self, disposition: str, text: Optional[str], confidence: Optional[float]):
        """Send a bot turn response."""
        event: BotTurnResponseEvent = {
            'type': 'bot_turn_response',
            'data': {
                'disposition': disposition,
                'text': text,
                'confidence': confidence
            }
        }
        message = self.create_message('event', {'entities': [event]})
        print(f"{datetime.now().isoformat()}:[Session] Sending bot turn response: disposition={disposition}, text={text}, confidence={confidence}")
        asyncio.create_task(self.send(message))
    
    def send_transcript(self, transcript: str, confidence: float, is_final: bool):
        """Send a transcript event."""
        if not self.selected_media:
            return
        
        channel = self.selected_media.get('channels', ['external'])[0]
        
        transcript_data: TranscriptData = {
            'id': str(uuid4()),
            'channel': channel,
            'isFinal': is_final,
            'alternatives': [{
                'confidence': confidence,
                'interpretations': [{
                    'type': 'normalized',
                    'transcript': transcript
                }]
            }]
        }
        
        event: TranscriptEvent = {
            'type': 'transcript',
            'data': transcript_data
        }
        
        message = self.create_message('event', {'entities': [event]})
        print(f"{datetime.now().isoformat()}:[Session] Sending transcript: {transcript}, confidence={confidence}, isFinal={is_final}")
        asyncio.create_task(self.send(message))
    
    def send_disconnect(self, reason: str, info: str, output_variables: Dict[str, str]):
        """Send a disconnect message."""
        self._disconnecting = True
        print(f"{datetime.now().isoformat()}:[Session] Sending disconnect: reason={reason}, info={info}")
        
        message = self.create_message('disconnect', {
            'reason': reason,
            'info': info,
            'outputVariables': output_variables
        })
        asyncio.create_task(self.send(message))
    
    def send_closed(self):
        """Send a closed message."""
        message = self.create_message('closed', {})
        print(f"{datetime.now().isoformat()}:[Session] Sending closed message.")
        asyncio.create_task(self.send(message))
    
    def send_keep_alive(self):
        """Send a keep-alive (pong) message."""
        print(f"{datetime.now().isoformat()}:[Session] Sending keep-alive (pong) message.")
        message = self.create_message('pong', {})
        asyncio.create_task(self.send(message))
        if self.voice_ai_agent:
            asyncio.create_task(self.voice_ai_agent.send_keep_alive())
    
    async def process_binary_message(self, data: bytes):
        """Process incoming binary audio data."""
        if self._disconnecting or self._closed:
            print(f"{datetime.now().isoformat()}:[Session] Ignoring binary message: session disconnecting or closed.")
            return
        
        if self._is_capturing_dtmf:
            print(f"{datetime.now().isoformat()}:[Session] Ignoring binary message: capturing DTMF.")
            return
        
        if self.voice_ai_agent:
            await self.voice_ai_agent.process_audio(data)
    
    def process_dtmf(self, digit: str):
        """Process DTMF digit."""
        if self._disconnecting or self._closed:
            print(f"{datetime.now().isoformat()}:[Session] Ignoring DTMF: session disconnecting or closed.")
            return
        
        if self._is_audio_playing:
            print(f"{datetime.now().isoformat()}:[Session] Ignoring DTMF: audio is playing.")
            return
        
        if not self._is_capturing_dtmf:
            self._is_capturing_dtmf = True
            print(f"{datetime.now().isoformat()}:[Session] Started capturing DTMF.")
        
        print(f"{datetime.now().isoformat()}:[Session] Processing DTMF digit: {digit}")
        # TODO: Implement DTMF service if needed
