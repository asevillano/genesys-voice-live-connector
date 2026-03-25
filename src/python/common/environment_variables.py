"""
Environment variables configuration
"""
import os

DEFAULT_PORT = 8080
DEFAULT_MAX_BINARY_MESSAGE_SIZE = 64000
DEFAULT_MIN_BINARY_MESSAGE_SIZE = 8000
DEFAULT_NO_INPUT_TIMEOUT = 30000


def get_port() -> int:
    """Get the server port from environment or default."""
    env_port = os.getenv("PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    return DEFAULT_PORT


def get_max_binary_message_size() -> int:
    """Get maximum binary message size from environment or default."""
    env_val = os.getenv("MAX_BINARY_MESSAGE_SIZE")
    if env_val:
        try:
            val = int(env_val)
            if val > 0:
                return val
        except ValueError:
            pass
        print(f"Invalid MAX_BINARY_MESSAGE_SIZE, using default: {DEFAULT_MAX_BINARY_MESSAGE_SIZE}")
    return DEFAULT_MAX_BINARY_MESSAGE_SIZE


def get_min_binary_message_size() -> int:
    """Get minimum binary message size from environment or default."""
    env_val = os.getenv("MIN_BINARY_MESSAGE_SIZE")
    if env_val:
        try:
            val = int(env_val)
            if val > 0:
                return val
        except ValueError:
            pass
        print(f"Invalid MIN_BINARY_MESSAGE_SIZE, using default: {DEFAULT_MIN_BINARY_MESSAGE_SIZE}")
    return DEFAULT_MIN_BINARY_MESSAGE_SIZE


def get_no_input_timeout() -> int:
    """Get no input timeout from environment or default (in milliseconds)."""
    env_val = os.getenv("NO_INPUT_TIMEOUT")
    if env_val:
        try:
            val = int(env_val)
            if val > 0:
                return val
        except ValueError:
            pass
        print(f"Invalid NO_INPUT_TIMEOUT, using default: {DEFAULT_NO_INPUT_TIMEOUT}")
    return DEFAULT_NO_INPUT_TIMEOUT
