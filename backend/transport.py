import asyncio
import serial
from backend.protocol import encode, decode, MAX_LINE


class SerialDevice:
    """Reconnects indefinitely. Firmware must implement protocol/README.md."""
    def __init__(self, port, baud=115200):
        self.port, self.baud, self.link = port, baud, None
        self.lock = asyncio.Lock()

    async def messages(self):
        while True:
            try:
                self.link = await asyncio.to_thread(serial.Serial, self.port, self.baud, timeout=.25, write_timeout=1)
                await self.command({'t': 'hello', 'protocol': 1})
                pending = b''
                while True:
                    chunk = await asyncio.to_thread(self.link.read, min(self.link.in_waiting + 1, 8192))
                    pending += chunk
                    if len(pending) > MAX_LINE:
                        raise ValueError('Oversized serial frame')
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        if line:
                            yield decode(line)
            except (serial.SerialException, OSError, ValueError) as exc:
                yield {'t': 'disconnected', 'reason': str(exc)}
                await asyncio.sleep(2)
            finally:
                if self.link:
                    self.link.close()
                    self.link = None

    async def command(self, cmd):
        async with self.lock:
            if not self.link or not self.link.is_open:
                raise ValueError('Board not linked')
            await asyncio.to_thread(self.link.write, encode(cmd))
