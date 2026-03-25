"""
Voice Live Agent - Azure Voice Live API integration

This module handles the connection to Azure Voice Live API (Realtime API with Azure Speech voices)
and converts audio between µ-law 8kHz (Genesys) and PCM16 24kHz (Voice Live).
"""
import os
import json
import base64
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any

import websockets
from websockets.client import WebSocketClientProtocol

from .voice_agent_base import VoiceAIAgentBase
from .audio_converter import ulaw_to_pcm16_24khz, pcm16_24khz_to_ulaw
from .cosmos_db import get_invoices
from ..common.environment_variables import get_no_input_timeout

if TYPE_CHECKING:
    from ..websocket.session import Session

# Voice Live API Configuration
VOICE_LIVE_ENDPOINT = os.getenv('AZURE_VOICE_LIVE_ENDPOINT', '')
VOICE_LIVE_API_KEY = os.getenv('AZURE_VOICE_LIVE_API_KEY', '')
VOICE_LIVE_MODEL = os.getenv('VOICE_LIVE_MODEL', 'gpt-realtime')
VOICE_LIVE_API_VERSION = os.getenv('AZURE_VOICE_LIVE_API_VERSION', '2025-10-01')
VOICE_LIVE_VOICE = os.getenv('AZURE_VOICE_LIVE_VOICE', 'es-ES-Ximena:DragonHDLatestNeural')
INITIAL_GREETING = os.getenv('INITIAL_GREETING', 'Hello')

# Event types to log with full details
LOG_EVENT_TYPES = [
    'error',
    'session.created',
    'session.updated',
    'response.created',
    'response.done',
    'response.audio.done',
    'input_audio_buffer.speech_started',
    'input_audio_buffer.speech_stopped',
    'conversation.item.created',
    'conversation.item.input_audio_transcription.completed',
]


def build_voice_live_endpoint() -> str:
    """Build the Voice Live WebSocket endpoint URL."""
    if not VOICE_LIVE_ENDPOINT:
        return ''
    
    # Remove trailing slash
    base_endpoint = VOICE_LIVE_ENDPOINT.rstrip('/')
    
    # Convert https to wss
    ws_endpoint = base_endpoint.replace('https://', 'wss://')
    
    # Build full WebSocket URL
    full_endpoint = f"{ws_endpoint}/voice-live/realtime?api-version={VOICE_LIVE_API_VERSION}&model={VOICE_LIVE_MODEL}"
    
    print(f"{datetime.now().isoformat()}:[VoiceLive]Built endpoint: {full_endpoint}")
    return full_endpoint


def is_azure_speech_voice(voice: str) -> bool:
    """Check if voice is an Azure Speech voice."""
    import re
    return ':' in voice or re.match(r'^[a-z]{2}-[A-Z]{2}-', voice, re.IGNORECASE) is not None


class VoiceLiveAgent(VoiceAIAgentBase):
    """Voice Live Agent implementation for Azure Voice Live API."""
    
    def __init__(self, session: 'Session'):
        # Validate configuration
        if not VOICE_LIVE_API_KEY:
            raise ValueError('[VoiceLive] Missing API key. Set AZURE_VOICE_LIVE_API_KEY in .env')
        if not VOICE_LIVE_ENDPOINT:
            raise ValueError('[VoiceLive] Missing endpoint. Set AZURE_VOICE_LIVE_ENDPOINT in .env')
        
        # Initialize base class with no-input callback
        super().__init__(
            session,
            self._on_no_input_timeout,
            get_no_input_timeout()
        )
        
        self.endpoint = build_voice_live_endpoint()
        self.voice_live_ws: Optional[WebSocketClientProtocol] = None
        self.pending_function_call: Optional[Dict[str, Any]] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        print(f"{datetime.now().isoformat()}:[VoiceLive]Endpoint: {self.endpoint}")
        print(f"{datetime.now().isoformat()}:[VoiceLive]Voice: {VOICE_LIVE_VOICE}")
        print(f"{datetime.now().isoformat()}:[VoiceLive]Model: {VOICE_LIVE_MODEL}")
        
        # Start connection in background
        asyncio.create_task(self._connect())
    
    def _on_no_input_timeout(self):
        """Called when no input timer expires."""
        print(f"{datetime.now().isoformat()}:[VoiceLive]NoInputTimer:Timeout reached, sending response.create")
        if self._is_agent_connected():
            asyncio.create_task(self._send_no_input_message())
    
    async def _send_no_input_message(self):
        """Send no input message to Voice Live."""
        if not self._is_agent_connected():
            return
        
        no_input_item = {
            'type': 'conversation.item.create',
            'item': {
                'type': 'message',
                'role': 'user',
                'content': [{
                    'type': 'input_text',
                    'text': os.getenv('NO_INPUT_MESSAGE', 'User did not provide any input. Act accordingly.')
                }]
            }
        }
        print(f"{datetime.now().isoformat()}:[VoiceLive]Sending No Input conversation item")
        await self.voice_live_ws.send(json.dumps(no_input_item))
        await self.voice_live_ws.send(json.dumps({'type': 'response.create'}))
    
    async def _connect(self):
        """Connect to Voice Live WebSocket."""
        print(f"{datetime.now().isoformat()}:[VoiceLive]Connecting to WebSocket...")
        
        try:
            self.voice_live_ws = await websockets.connect(
                self.endpoint,
                additional_headers={'api-key': VOICE_LIVE_API_KEY}
            )
            print(f"{datetime.now().isoformat()}:[VoiceLive]Connected to Voice Live API")
            
            # Wait a bit for connection to stabilize (like TypeScript setTimeout 100ms)
            await asyncio.sleep(0.1)
            
            # Initialize session first
            await self._initialize_session()
            
            # Then start receiving messages
            self._receive_task = asyncio.create_task(self._receive_messages())
            
        except Exception as e:
            print(f"{datetime.now().isoformat()}:[VoiceLive]WebSocket error: {e}")
    
    async def _initialize_session(self):
        """Initialize the Voice Live session."""
        # Configure voice
        if is_azure_speech_voice(VOICE_LIVE_VOICE):
            voice_config = {'type': 'azure-standard', 'name': VOICE_LIVE_VOICE}
        else:
            voice_config = VOICE_LIVE_VOICE
        
        session_update = {
            'type': 'session.update',
            'session': {
                'modalities': ['text', 'audio'],
                'instructions': self._get_system_message(),
                'voice': voice_config,
                'input_audio_format': 'pcm16',
                'output_audio_format': 'pcm16',
                'turn_detection': {
                    'type': 'server_vad',
                    'threshold': 0.5,
                    'prefix_padding_ms': 300,
                    'silence_duration_ms': 700,
                    'create_response': True,
                    'interrupt_response': True
                },
                'input_audio_echo_cancellation': {
                    'type': 'server_echo_cancellation'
                },
                'input_audio_noise_reduction': {
                    'type': 'azure_deep_noise_suppression'
                },
                'input_audio_transcription': {
                    'model': 'whisper-1'
                },
                'tools': self._get_system_tools(),
                'tool_choice': 'auto',
                'temperature': 0.8
            }
        }
        
        print(f"{datetime.now().isoformat()}:[VoiceLive]InitializeSession: {json.dumps(session_update)[:500]}")
        await self.voice_live_ws.send(json.dumps(session_update))
    
    async def _send_initial_greeting(self):
        """Send the initial greeting to start the conversation."""
        initial_item = {
            'type': 'conversation.item.create',
            'item': {
                'type': 'message',
                'role': 'user',
                'content': [{
                    'type': 'input_text',
                    'text': INITIAL_GREETING
                }]
            }
        }
        
        print(f"{datetime.now().isoformat()}:[VoiceLive]Sending initial greeting")
        await self.voice_live_ws.send(json.dumps(initial_item))
        await self.voice_live_ws.send(json.dumps({'type': 'response.create'}))
    
    async def _receive_messages(self):
        """Receive and process messages from Voice Live."""
        try:
            async for message in self.voice_live_ws:
                try:
                    response = json.loads(message)
                    event_type = response.get('type', '')
                    
                    # Log events (skip verbose audio events)
                    if event_type in LOG_EVENT_TYPES:
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Event: {event_type} {json.dumps(response)[:500]}")
                    elif event_type not in ['response.audio.delta', 'response.audio_transcript.delta']:
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Event: {event_type}")
                    
                    # Handle session updated - start greeting
                    if event_type == 'session.updated':
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Session configured")
                        await self._send_initial_greeting()
                    
                    # Handle audio delta
                    elif event_type == 'response.audio.delta' and response.get('delta'):
                        # print(f"{datetime.now().isoformat()}:[VoiceLive]Received audio delta")
                        ulaw_data = pcm16_24khz_to_ulaw(response['delta'])
                        self.session.send_audio(ulaw_data)
                    
                    # Handle user input transcription
                    elif event_type == 'conversation.item.input_audio_transcription.completed':
                        transcript = response.get('transcript', '') or ''
                        if not transcript:
                            item_content = response.get('item', {}).get('content', [{}])
                            if item_content:
                                transcript = item_content[0].get('transcript', '')
                        if transcript:
                            print(f"{datetime.now().isoformat()}:[VoiceLive][USER_INPUT] Transcription: \"{transcript}\"")
                    
                    # Handle response done
                    elif event_type == 'response.done':
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Response done")
                        self.session.flush_buffer()
                        
                        # Check for failed response (rate limits, errors)
                        resp_obj = response.get('response', {})
                        if resp_obj.get('status') == 'failed':
                            error_details = resp_obj.get('status_details', {}).get('error', {})
                            print(f"{datetime.now().isoformat()}:[VoiceLive]Response FAILED: {json.dumps(error_details)}")
                            self.session.send_disconnect('error', 'RateLimitError', error_details)
                            return
                        
                        # Log LLM text response
                        if resp_obj.get('output'):
                            for out_item in resp_obj['output']:
                                for content in out_item.get('content', []):
                                    if content.get('transcript'):
                                        print(f"{datetime.now().isoformat()}:[VoiceLive][LLM_RESPONSE] Text: \"{content['transcript']}\"")
                        
                        # Process function calls
                        if resp_obj.get('output'):
                            for output in resp_obj['output']:
                                if output.get('type') == 'function_call':
                                    await self._handle_function_call(output)
                    
                    # Handle conversation item created (for function calls)
                    elif event_type == 'conversation.item.created':
                        if response.get('item', {}).get('type') == 'function_call':
                            self.pending_function_call = {
                                'name': response['item'].get('name'),
                                'call_id': response['item'].get('call_id')
                            }
                            print(f"{datetime.now().isoformat()}:[VoiceLive]Function call detected: {self.pending_function_call['name']}")
                    
                    # Handle function call arguments
                    elif event_type == 'response.function_call_arguments.done':
                        if self.pending_function_call:
                            self.pending_function_call['arguments'] = response.get('arguments')
                    
                    # Handle speech events
                    elif event_type == 'input_audio_buffer.speech_started':
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Speech started - sending barge-in")
                        self.no_input_timer.halt_timer()
                        self.session.send_barge_in()
                        self.session.set_is_audio_playing(True)
                    
                    elif event_type == 'input_audio_buffer.speech_stopped':
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Speech stopped")
                        self.no_input_timer.resume_timer()
                    
                    # Handle errors
                    elif event_type == 'error':
                        print(f"{datetime.now().isoformat()}:[VoiceLive]Error: {response.get('error', {}).get('message')}")
                    
                except Exception as e:
                    print(f"{datetime.now().isoformat()}:[VoiceLive]Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"{datetime.now().isoformat()}:[VoiceLive]WebSocket closed: {e}")
    
    async def _handle_function_call(self, func_call: Dict[str, Any]):
        """Handle a function call from the model."""
        args = json.loads(func_call.get('arguments', '{}'))
        func_name = func_call.get('name', '')
        call_id = func_call.get('call_id', '')
        
        print(f"{datetime.now().isoformat()}:[VoiceLive]FunctionCall: {func_name} {json.dumps(args)}")
        
        response_data = {
            'type': 'conversation.item.create',
            'item': {
                'type': 'function_call_output',
                'call_id': call_id,
                'output': ''
            }
        }
        
        if func_name == 'getInvoices' or func_name == 'get_billing_info':
            try:
                output = await get_invoices(args)
                response_data['item']['output'] = json.dumps(output)
                print(f"{datetime.now().isoformat()}:[VoiceLive]getInvoices result: {json.dumps(output)}")
            except Exception as e:
                print(f"{datetime.now().isoformat()}:[VoiceLive]getInvoices error: {e}")
                response_data['item']['output'] = json.dumps({'status': 'error', 'error': 'Failed to retrieve invoices'})
        
        elif func_name == 'transferToAgent':
            response_data['item']['output'] = json.dumps({'status': 'ok'})
            self.session.send_disconnect('completed', args.get('process', 'transfer'), {})
        
        elif func_name == 'endCall':
            print(f"{datetime.now().isoformat()}:[VoiceLive]endCall received - responding OK and scheduling disconnect")
            
            # Respond OK to the function call so the model can generate farewell audio
            response_data['item']['output'] = json.dumps({'status': 'ok'})
            await self.voice_live_ws.send(json.dumps(response_data))
            await self.voice_live_ws.send(json.dumps({'type': 'response.create'}))
            
            # Wait for farewell audio to be generated and played, then disconnect
            farewell_delay = float(os.getenv('FAREWELL_DELAY_SECONDS', '8'))
            asyncio.create_task(self._delayed_disconnect(farewell_delay))
            return
        
        else:
            response_data['item']['output'] = json.dumps({'status': 'unknown_function'})
        
        await self.voice_live_ws.send(json.dumps(response_data))
        await self.voice_live_ws.send(json.dumps({'type': 'response.create'}))
    
    def _is_agent_connected(self) -> bool:
        """Check if WebSocket is connected."""
        if self.voice_live_ws is None:
            return False
        try:
            from websockets.protocol import State
            return self.voice_live_ws.state == State.OPEN
        except:
            # Fallback for different websockets versions
            return self.voice_live_ws is not None
    
    async def _delayed_disconnect(self, delay_seconds: float) -> None:
        """Wait for delay then disconnect the call."""
        await asyncio.sleep(delay_seconds)
        print(f"{datetime.now().isoformat()}:[VoiceLive]Disconnecting after farewell delay")
        self.session.send_disconnect('completed', 'EndCall', {})
    
    async def send_keep_alive(self) -> None:
        """Voice Live handles keep-alive internally."""
        pass
    
    async def process_audio(self, audio_payload: bytes) -> None:
        """Process incoming audio from Genesys."""
        if self._is_agent_connected():
            # Convert µ-law 8kHz to PCM16 24kHz
            pcm_24khz = ulaw_to_pcm16_24khz(audio_payload)
            audio_base64 = base64.b64encode(pcm_24khz).decode('utf-8')
            
            audio_append = {
                'type': 'input_audio_buffer.append',
                'audio': audio_base64
            }
            await self.voice_live_ws.send(json.dumps(audio_append))
    
    async def process_playback_completed(self) -> None:
        """Handle playback completion."""
        if self._is_agent_connected():
            print(f"{datetime.now().isoformat()}:[VoiceLive]PlaybackCompleted - starting no input timer")
            self.no_input_timer.start_timer()
    
    async def close(self) -> None:
        """Close the Voice Live connection."""
        # Stop the no input timer first
        self.no_input_timer.halt_timer()
        
        if self._is_agent_connected():
            print(f"{datetime.now().isoformat()}:[VoiceLive]Closing connection")
            if self._receive_task:
                self._receive_task.cancel()
            await self.voice_live_ws.close()
