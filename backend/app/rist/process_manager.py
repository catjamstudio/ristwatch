import asyncio
from collections.abc import AsyncIterator, Sequence


class RistProcessManager:
    """Owns a libRIST subprocess without interpreting its telemetry output."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self, command: Sequence[str]) -> None:
        if self.running:
            raise RuntimeError("RIST process is already running")
        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    async def output_lines(self) -> AsyncIterator[str]:
        if self._process is None or self._process.stdout is None:
            return
        while line := await self._process.stdout.readline():
            yield line.decode("utf-8", errors="replace").rstrip()

    async def stop(self, timeout: float = 5) -> None:
        if not self.running or self._process is None:
            return
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()

