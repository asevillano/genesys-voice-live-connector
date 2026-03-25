"""
Voice AI Agent Factory
"""
import os
from typing import TYPE_CHECKING

from .voice_agent_base import VoiceAIAgentBase
from .voice_live import VoiceLiveAgent

if TYPE_CHECKING:
    from ..websocket.session import Session


class VoiceAIAgentFactory:
    """Factory for creating Voice AI Agent instances."""
    
    @staticmethod
    def create(agent_name: str, session: 'Session') -> VoiceAIAgentBase:
        """
        Create a Voice AI Agent based on the agent name.
        
        Args:
            agent_name: Name of the agent type ('voicelive', 'openai', 'deepgram')
            session: WebSocket session
            
        Returns:
            VoiceAIAgentBase instance
        """
        from datetime import datetime
        
        name = (agent_name or 'voicelive').lower()
        
        if name in ('voicelive', 'voice-live'):
            print(f"{datetime.now().isoformat()}:[VoiceAIAgentFactory] Creating VoiceLiveAgent (Azure Speech voices).")
            return VoiceLiveAgent(session)
        else:
            raise ValueError(f"[VoiceAIAgentFactory] Unknown BOT_TYPE: {agent_name}")
