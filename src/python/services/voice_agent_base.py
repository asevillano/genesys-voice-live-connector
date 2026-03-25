"""
Base class for Voice AI Agents
"""
import os
import json
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Optional

from .timer import Timer

if TYPE_CHECKING:
    from ..websocket.session import Session


class VoiceAIAgentBase(ABC):
    """
    Base class for all voice AI agents, providing common session and timeout handling.
    """
    
    def __init__(
        self, 
        session: 'Session', 
        no_input_callback: Callable[[], None],
        no_input_timeout: int = 30000
    ):
        """
        Initialize the voice AI agent.
        
        Args:
            session: WebSocket session for client communication
            no_input_callback: Callback to invoke when no input timer elapses
            no_input_timeout: Timeout in milliseconds
        """
        self.session = session
        self.no_input_timer = Timer(no_input_callback, no_input_timeout)
    
    @abstractmethod
    async def process_audio(self, audio_payload: bytes) -> None:
        """Process incoming audio buffer."""
        pass
    
    @abstractmethod
    async def send_keep_alive(self) -> None:
        """Send Keep Alive Message to the Agent Platform."""
        pass
    
    async def process_playback_completed(self) -> None:
        """
        Handle completion of playback.
        Default implementation: start no-input timer if agent is connected.
        """
        if self._is_agent_connected():
            from datetime import datetime
            print(f"{datetime.now().isoformat()}:PlaybackCompleted|Starting no input timer")
            self.no_input_timer.start_timer()
    
    @abstractmethod
    async def close(self) -> None:
        """Close any open resources and cleanup."""
        pass
    
    @abstractmethod
    def _is_agent_connected(self) -> bool:
        """Returns true if the underlying agent connection is open."""
        pass
    
    def _get_system_message(self) -> str:
        """Load and process the system message from prompt files."""
        input_vars = self.session.get_input_variables()
        prompt_name = input_vars.get('promptName', 'Default')
        prompt_filename = f"{prompt_name}Prompt.md"
        file_path = f"./src/prompts/{prompt_filename}"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = f.read()
            
            # Replace template variables
            for key, value in input_vars.items():
                file_data = file_data.replace(f"{{{{{key}}}}}", str(value))
            
            # Replace date
            from datetime import datetime
            now = datetime.now()
            file_data = file_data.replace("{{current_date}}", f"{now.year}-{now.month}-{now.day}")
            
            # Remove comments and trailing commas, then return as string
            cleaned = re.sub(r'/\*[\s\S]*?\*/', '', file_data)  # Multi-line comments
            cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)  # Single-line comments
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)  # Trailing commas
            
            # Validate JSON but return as string (Voice Live API expects string)
            try:
                json.loads(cleaned)  # Validate it's valid JSON
            except json.JSONDecodeError as e:
                print(f"[VoiceAIAgent] Warning: prompt file is not valid JSON: {e}")
            
            return cleaned
                
        except FileNotFoundError:
            print(f"[VoiceAIAgent] File not found: {file_path}")
            return os.getenv(
                'DEFAULT_PROMPT_INSTRUCTIONS', 
                "You are a helpful assistant. Please answer the user's questions to the best of your ability."
            )
        except Exception as e:
            print(f"[VoiceAIAgent] Error reading system message from file {file_path}: {e}")
            return os.getenv(
                'DEFAULT_PROMPT_INSTRUCTIONS',
                "You are a helpful assistant. Please answer the user's questions to the best of your ability."
            )
    
    def _get_system_tools(self) -> list:
        """Load tools configuration from JSON file."""
        input_vars = self.session.get_input_variables()
        prompt_name = input_vars.get('promptName', 'Default')
        tools_filename = f"{prompt_name}Tools.json"
        file_path = f"./src/prompts/{tools_filename}"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_data = f.read()
            
            # Remove comments and trailing commas for JSON compatibility
            cleaned = re.sub(r'/\*[\s\S]*?\*/', '', file_data)
            cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            
            return json.loads(cleaned)
        except FileNotFoundError:
            print(f"[VoiceAIAgent] Tools file not found: {file_path}")
            return []
        except Exception as e:
            print(f"[VoiceAIAgent] Error reading tools from file {file_path}: {e}")
            return []
