
import asyncio
from websockets.exceptions import ConnectionClosed, InvalidStatus

RECONNECT_DELAYS = (1.0, 2.0, 4.0)


class GeminiDisconnected(ConnectionError):
    """The receive stream ended without a pending application shutdown."""


class GeminiSetupError(RuntimeError):
    def __init__(self, code=None):
        self.code = code
        super().__init__(f"Gemini không xác nhận setupComplete (code={code}).")


def is_retryable_connection_error(error):
    # Called only for network operations, never for microphone/device failures.
    if isinstance(error, GeminiSetupError):
        return error.code in (429, 500, 502, 503, 504)
    if isinstance(error, ConnectionClosed):
        code = error.rcvd.code if error.rcvd is not None else None
        return code in (None, 1000, 1001, 1006, 1011, 1012, 1013, 1014)
    if isinstance(error, InvalidStatus):
        return error.response.status_code in (408, 429, 500, 502, 503, 504)
    return isinstance(error, (OSError, asyncio.TimeoutError))
