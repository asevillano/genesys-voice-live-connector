"""Protocol types and definitions for Genesys AudioConnector"""
from typing import TypedDict, List, Literal, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from uuid import uuid4

# Type aliases
Uuid = str
SequenceNumber = int
Duration = str  # ISO8601 duration format: PT{number}S

# Media types
MediaChannel = Literal['external', 'internal']
MediaType = Literal['audio']
MediaFormat = Literal['PCMU', 'L16']
MediaRate = Literal[8000]


class MediaParameter(TypedDict):
    type: MediaType
    format: MediaFormat
    channels: List[MediaChannel]
    rate: MediaRate


# Message types
CloseReason = Literal['end', 'error', 'disconnect', 'reconnect']
DisconnectReason = Literal['completed', 'unauthorized', 'error']
ErrorCode = Literal[400, 405, 408, 409, 413, 415, 429, 500, 503]


class Participant(TypedDict):
    id: Uuid
    ani: str
    aniName: str
    dnis: str


class OpenParameters(TypedDict):
    organizationId: Uuid
    conversationId: Uuid
    participant: Participant
    media: List[MediaParameter]
    language: Optional[str]
    customConfig: Optional[Dict[str, Any]]
    inputVariables: Optional[Dict[str, str]]


class OpenedParameters(TypedDict):
    media: List[MediaParameter]
    discardTo: Optional[Duration]
    startPaused: Optional[bool]


class DisconnectParameters(TypedDict):
    reason: DisconnectReason
    info: Optional[str]
    outputVariables: Optional[Dict[str, str]]


class CloseParameters(TypedDict):
    reason: CloseReason


class PingParameters(TypedDict):
    rtt: Optional[Duration]


class ErrorParameters(TypedDict):
    code: ErrorCode
    message: str
    retryAfter: Optional[Duration]


class EventEntity(TypedDict):
    type: str
    data: Dict[str, Any]


class EventParameters(TypedDict):
    entities: List[EventEntity]


class DTMFParameters(TypedDict):
    digit: str
    duration: Duration
    position: Duration


# Base message classes
@dataclass
class MessageBase:
    version: str = '2'
    id: str = ''
    type: str = ''
    seq: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClientMessage(MessageBase):
    serverseq: int = 0
    position: str = 'PT0S'


@dataclass
class ServerMessage(MessageBase):
    clientseq: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'id': self.id,
            'type': self.type,
            'seq': self.seq,
            'clientseq': self.clientseq,
            'parameters': self.parameters
        }


# Event entity types for voice bots
class BargeInData(TypedDict):
    pass  # Empty


class BargeInEvent(TypedDict):
    type: Literal['barge_in']
    data: BargeInData


BotTurnDisposition = Literal['continue', 'final', 'error']


class BotTurnResponseData(TypedDict):
    disposition: BotTurnDisposition
    text: Optional[str]
    confidence: Optional[float]


class BotTurnResponseEvent(TypedDict):
    type: Literal['bot_turn_response']
    data: BotTurnResponseData


class TranscriptAlternative(TypedDict):
    confidence: float
    interpretations: List[Dict[str, str]]


class TranscriptData(TypedDict):
    id: str
    channel: MediaChannel
    isFinal: bool
    alternatives: List[TranscriptAlternative]


class TranscriptEvent(TypedDict):
    type: Literal['transcript']
    data: TranscriptData
