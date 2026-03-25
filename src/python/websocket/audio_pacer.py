"""
Audio Paced Sender - Sends audio at a controlled rate to avoid buffer issues
"""
import asyncio
from datetime import datetime
from typing import List, Optional
import websockets


class AudioPacedSender:
    """
    Sends audio data at a paced rate to match playback speed.
    """
    
    def __init__(
        self,
        ws,  # WebSocket connection
        sample_rate_hz: int = 8000,
        channels: int = 2,
        bytes_per_sample: int = 2,
        target_chunk_duration_ms: int = 250,
        max_binary_message_size: int = 64 * 1024
    ):
        self.ws = ws
        self.sample_rate_hz = sample_rate_hz
        self.channels = channels
        self.bytes_per_sample = bytes_per_sample
        self.target_chunk_duration_ms = target_chunk_duration_ms
        self.max_binary_message_size = max_binary_message_size
        
        self.buffer: List[bytes] = []
        self.buffered_bytes = 0
        self._task: Optional[asyncio.Task] = None
        self._last_send_at = 0.0
    
    @property
    def target_chunk_bytes(self) -> int:
        """Bytes that correspond to one pacing interval."""
        bytes_per_ms = (self.sample_rate_hz * self.channels * self.bytes_per_sample) / 1000
        return int(bytes_per_ms * self.target_chunk_duration_ms)
    
    def enqueue(self, chunk: bytes):
        """Add audio chunk to the buffer."""
        if not chunk:
            return
        self.buffer.append(chunk)
        self.buffered_bytes += len(chunk)
        if self._task is None:
            self._start_pacer()
    
    def _start_pacer(self):
        """Start the paced sending loop."""
        self._last_send_at = asyncio.get_event_loop().time()
        self._task = asyncio.create_task(self._pacer_loop())
    
    async def _pacer_loop(self):
        """Main pacing loop."""
        try:
            while True:
                # Check WebSocket state - use try/except for compatibility
                try:
                    from websockets.protocol import State
                    ws_is_open = self.ws.state == State.OPEN
                except:
                    ws_is_open = True  # Assume open if we can't check
                
                if not ws_is_open:
                    self._stop_pacer()
                    return
                
                # If nothing buffered, pause
                if self.buffered_bytes == 0:
                    self._stop_pacer()
                    return
                
                # Build chunk to send
                to_send = self._take_bytes(min(self.target_chunk_bytes, self.max_binary_message_size))
                
                try:
                    # print(f"{datetime.now().isoformat()}:[AudioPacer] Sending {len(to_send)} bytes")
                    await self.ws.send(to_send)
                except Exception as e:
                    print(f"{datetime.now().isoformat()}:[AudioPacer] Error sending: {e}")
                    self._stop_pacer()
                    return
                
                # Calculate next send time
                self._last_send_at += self.target_chunk_duration_ms / 1000.0
                now = asyncio.get_event_loop().time()
                delay = max(0, self._last_send_at - now)
                
                await asyncio.sleep(delay)
                
        except asyncio.CancelledError:
            pass
    
    def _stop_pacer(self):
        """Stop the pacer."""
        if self._task:
            self._task.cancel()
            self._task = None
    
    def _take_bytes(self, n: int) -> bytes:
        """Take up to n bytes from the buffer."""
        n = min(n, self.buffered_bytes)
        if n <= 0:
            return b''
        
        result = bytearray(n)
        written = 0
        
        while written < n and self.buffer:
            head = self.buffer[0]
            remaining = n - written
            
            if len(head) <= remaining:
                result[written:written + len(head)] = head
                written += len(head)
                self.buffer.pop(0)
            else:
                result[written:written + remaining] = head[:remaining]
                self.buffer[0] = head[remaining:]
                written += remaining
        
        self.buffered_bytes -= written
        return bytes(result[:written])
    
    def flush_all(self):
        """Clear all buffered audio."""
        self.buffer.clear()
        self.buffered_bytes = 0
        self._stop_pacer()
