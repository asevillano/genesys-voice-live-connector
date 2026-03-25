"""
Timer utility for handling timeouts
"""
import asyncio
from typing import Callable, Optional, Awaitable, Union


class Timer:
    """
    A timer that invokes a callback after a specified delay.
    Supports halting, resuming, starting, and stopping.
    """
    
    def __init__(self, callback: Callable[[], Union[None, Awaitable[None]]], delay_ms: int):
        """
        Initialize the timer.
        
        Args:
            callback: Function to invoke when timer elapses (can be sync or async)
            delay_ms: Timeout in milliseconds
        """
        self.callback = callback
        self.delay_ms = delay_ms
        self.timer_halted = False
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    async def _timer_task(self):
        """Internal async task that waits and then calls callback."""
        try:
            await asyncio.sleep(self.delay_ms / 1000.0)
            result = self.callback()
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            pass
    
    def start_timer(self):
        """Start the timer. If already running, restart it."""
        if self.timer_halted:
            print(f"[NoInputTimer]StartTimer Triggered| Timer is halted, not starting again.")
            return
        
        print(f"[NoInputTimer]StartTimer Triggered| current Task: {self._task}| Which will be cancelled now.")
        self.stop_timer()
        
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._timer_task())
        except RuntimeError:
            # No running loop, try to get or create one
            pass
    
    def stop_timer(self):
        """Stop the timer if running."""
        if self._task is not None:
            print(f"[NoInputTimer]StopTimer Triggered| current Task: {self._task}| Which will be cancelled now.")
            self._task.cancel()
            self._task = None
    
    def halt_timer(self):
        """Halt the timer, preventing it from starting again."""
        print(f"[NoInputTimer]HaltTimer Triggered| Current Timer Halt State: {self.timer_halted}| current Task: {self._task}| Which will be cancelled now.")
        self.timer_halted = True
        self.stop_timer()
    
    def resume_timer(self):
        """Resume the timer (allow it to be started again)."""
        print(f"[NoInputTimer]ResumeTimer Triggered| Current Timer Halt State: {self.timer_halted}| current Task: {self._task}")
        self.timer_halted = False
        self.stop_timer()
