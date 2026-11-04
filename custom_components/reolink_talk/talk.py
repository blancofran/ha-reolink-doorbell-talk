"""RTSP (ONVIF backchannel) client that sends G.711 mu-law audio to the doorbell.

This module has no Home Assistant imports on purpose, so it can be tested alone.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import struct
import time
from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)

FRAME_BYTES = 160  # 20 ms of PCMU at 8 kHz
FRAME_SECONDS = 0.02
MAX_BUFFER_FRAMES = 10  # 200 ms; older audio is dropped so the delay can never grow
PREBUFFER_FRAMES = 2
_REQUIRE = "Require: www.onvif.org/ver20/backchannel"


class BackchannelError(Exception):
    """The doorbell could not open or keep the voice channel."""


class BackchannelClient:
    """Minimal RTSP client with Digest auth and an interleaved (TCP) audio track."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        path: str = "h264Preview_01_sub",
        port: int = 554,
    ) -> None:
        """Initialise the client."""
        self._host = host
        self._port = port
        self._user = username
        self._pwd = password
        self._url = f"rtsp://{host}:{port}/{path}"
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._cseq = 0
        self._session: str | None = None
        self._realm = ""
        self._nonce = ""
        self._qop = ""
        self._nc = 0
        self._channel = 0
        self._seq = int.from_bytes(os.urandom(2), "big")
        self._ts = int.from_bytes(os.urandom(4), "big")
        self._ssrc = int.from_bytes(os.urandom(4), "big")
        self._drain_task: asyncio.Task | None = None
        self.on_closed: Callable[[], None] | None = None

    # ---- Digest -----------------------------------------------------------
    def _auth_header(self, method: str, uri: str) -> str:
        ha1 = hashlib.md5(f"{self._user}:{self._realm}:{self._pwd}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        if self._qop:
            self._nc += 1
            nc = f"{self._nc:08x}"
            cnonce = os.urandom(8).hex()
            resp = hashlib.md5(
                f"{ha1}:{self._nonce}:{nc}:{cnonce}:auth:{ha2}".encode()
            ).hexdigest()
            return (
                f'Digest username="{self._user}", realm="{self._realm}", '
                f'nonce="{self._nonce}", uri="{uri}", response="{resp}", '
                f'qop=auth, nc={nc}, cnonce="{cnonce}"'
            )
        resp = hashlib.md5(f"{ha1}:{self._nonce}:{ha2}".encode()).hexdigest()
        return (
            f'Digest username="{self._user}", realm="{self._realm}", '
            f'nonce="{self._nonce}", uri="{uri}", response="{resp}"'
        )

    # ---- RTSP plumbing ----------------------------------------------------
    async def _request(
        self, method: str, extra: list[str] | None = None, url: str | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        assert self._writer is not None and self._reader is not None
        self._cseq += 1
        url = url or self._url
        lines = [f"{method} {url} RTSP/1.0", f"CSeq: {self._cseq}", "User-Agent: reolink_talk"]
        if self._session:
            lines.append(f"Session: {self._session}")
        lines += extra or []
        if self._nonce:
            lines.append(f"Authorization: {self._auth_header(method, url)}")
        self._writer.write(("\r\n".join(lines) + "\r\n\r\n").encode())
        await self._writer.drain()
        # The doorbell may send interleaved RTP/RTCP ("$" frames) before the reply: skip them.
        while True:
            first = await asyncio.wait_for(self._reader.readexactly(1), 8)
            if first != b"$":
                break
            header = await asyncio.wait_for(self._reader.readexactly(3), 8)
            await asyncio.wait_for(
                self._reader.readexactly(int.from_bytes(header[1:3], "big")), 8
            )
        raw = first + await asyncio.wait_for(self._reader.readuntil(b"\r\n\r\n"), 8)
        head = raw.decode(errors="replace").split("\r\n")
        status = int(head[0].split(" ", 2)[1])
        headers = {}
        for line in head[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        body = b""
        length = int(headers.get("content-length", "0") or 0)
        if length:
            body = await asyncio.wait_for(self._reader.readexactly(length), 8)
        return status, headers, body

    async def async_start(self) -> None:
        """Open the connection and start the voice (backchannel) track."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), 6
            )
            accept = ["Accept: application/sdp", _REQUIRE]
            status, headers, body = await self._request("DESCRIBE", accept)
            if status == 401:
                www = headers.get("www-authenticate", "")
                realm = re.search(r'realm="([^"]*)"', www)
                nonce = re.search(r'nonce="([^"]*)"', www)
                if not realm or not nonce:
                    raise BackchannelError("auth_unsupported")
                self._realm, self._nonce = realm.group(1), nonce.group(1)
                self._qop = "auth" if "qop" in www else ""
                status, headers, body = await self._request("DESCRIBE", accept)
            if status == 401:
                raise BackchannelError("invalid_auth")
            if status != 200:
                raise BackchannelError(f"describe_{status}")
            control = self._find_talk_control(body.decode(errors="replace"))
            base = headers.get("content-base", self._url).rstrip("/")
            track = control if control.startswith("rtsp://") else f"{base}/{control}"
            status, headers, _ = await self._request(
                "SETUP",
                [_REQUIRE, "Transport: RTP/AVP/TCP;unicast;interleaved=0-1"],
                url=track,
            )
            if status != 200:
                raise BackchannelError(f"setup_{status}")
            self._session = headers.get("session", "").split(";")[0] or None
            match = re.search(r"interleaved=(\d+)-(\d+)", headers.get("transport", ""))
            self._channel = int(match.group(1)) if match else 0
            status, _, _ = await self._request("PLAY", [_REQUIRE, "Range: npt=0.000-"])
            if status != 200:
                raise BackchannelError(f"play_{status}")
        except (OSError, TimeoutError, asyncio.IncompleteReadError, ValueError) as err:
            await self.async_stop()
            raise BackchannelError(f"connection: {err}") from err
        except BackchannelError:
            await self.async_stop()
            raise
        self._drain_task = asyncio.create_task(self._drain())

    @staticmethod
    def _find_talk_control(sdp: str) -> str:
        """Return the control URL of the audio track that accepts our voice."""
        sections = re.split(r"(?m)^(?=m=)", sdp)
        for section in sections:
            if section.startswith("m=audio") and "a=sendonly" in section:
                found = re.search(r"a=control:(\S+)", section)
                if found:
                    return found.group(1)
        raise BackchannelError("no_talk_track")

    async def _drain(self) -> None:
        """Read and discard whatever the doorbell sends (RTCP, replies)."""
        assert self._reader is not None
        try:
            while await self._reader.read(4096):
                pass
        except (OSError, asyncio.CancelledError):
            return
        finally:
            if self.on_closed:
                self.on_closed()

    # ---- audio ------------------------------------------------------------
    def send_frame(self, payload: bytes) -> None:
        """Send one 160 byte PCMU frame."""
        if self._writer is None or self._writer.is_closing():
            raise BackchannelError("closed")
        header = struct.pack(">BBHII", 0x80, 0, self._seq, self._ts, self._ssrc)
        packet = header + payload
        self._writer.write(b"$" + bytes([self._channel]) + struct.pack(">H", len(packet)) + packet)
        self._seq = (self._seq + 1) & 0xFFFF
        self._ts = (self._ts + len(payload)) & 0xFFFFFFFF

    async def async_stop(self) -> None:
        """Close the voice channel."""
        writer, self._writer = self._writer, None
        if self._drain_task:
            self._drain_task.cancel()
            self._drain_task = None
        if writer is None:
            return
        try:
            if self._session and not writer.is_closing():
                self._cseq += 1
                lines = [
                    f"TEARDOWN {self._url} RTSP/1.0",
                    f"CSeq: {self._cseq}",
                    f"Session: {self._session}",
                ]
                if self._nonce:
                    lines.append(f"Authorization: {self._auth_header('TEARDOWN', self._url)}")
                writer.write(("\r\n".join(lines) + "\r\n\r\n").encode())
                await asyncio.wait_for(writer.drain(), 1)
        except (OSError, TimeoutError):
            pass
        try:
            writer.close()
        except OSError:
            pass


class TalkSession:
    """Paces incoming audio to the doorbell and enforces time limits."""

    def __init__(
        self,
        client: BackchannelClient,
        on_close: Callable[[str], None],
        max_seconds: int = 120,
        idle_seconds: int = 15,
    ) -> None:
        """Initialise the session."""
        self._client = client
        self._on_close = on_close
        self._max = max_seconds
        self._idle = idle_seconds
        self._buf = bytearray()
        self._task: asyncio.Task | None = None
        self._closed = False
        self._started = 0.0
        self._last_audio = 0.0
        self.frames_sent = 0
        # Diagnostic counters (logged when the session closes).
        self._late_max = 0.0
        self._late_over = 0
        self._buf_high = 0
        self._underruns = 0
        self._dropped = 0
        self._feeds = 0
        self._gap_max = 0.0
        self._last_feed = 0.0
        client.on_closed = lambda: self._schedule_close("doorbell_closed")

    async def async_start(self) -> None:
        """Open the channel and start sending."""
        await self._client.async_start()
        now = time.monotonic()
        self._started = self._last_audio = now
        self._task = asyncio.create_task(self._run())

    def feed(self, data: bytes) -> None:
        """Queue mu-law bytes received from the browser."""
        if self._closed or not data:
            return
        now = time.monotonic()
        if self._last_feed:
            self._gap_max = max(self._gap_max, now - self._last_feed)
        self._last_feed = now
        self._feeds += 1
        self._last_audio = now
        self._buf.extend(data)
        self._buf_high = max(self._buf_high, len(self._buf) // FRAME_BYTES)
        overflow = len(self._buf) - MAX_BUFFER_FRAMES * FRAME_BYTES
        if overflow > 0:
            self._dropped += overflow
            del self._buf[:overflow]

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        next_t = loop.time()
        primed = False
        try:
            while not self._closed:
                now = time.monotonic()
                if now - self._started > self._max:
                    await self.async_close("max_time")
                    return
                if now - self._last_audio > self._idle:
                    await self.async_close("idle")
                    return
                if not primed and len(self._buf) >= PREBUFFER_FRAMES * FRAME_BYTES:
                    primed = True
                    next_t = loop.time()
                if primed:
                    if len(self._buf) >= FRAME_BYTES:
                        frame = bytes(self._buf[:FRAME_BYTES])
                        del self._buf[:FRAME_BYTES]
                        self._client.send_frame(frame)
                        self.frames_sent += 1
                    else:
                        primed = False
                        self._underruns += 1
                next_t += FRAME_SECONDS
                delay = next_t - loop.time()
                if delay < -0.2:
                    next_t = loop.time()
                    delay = 0
                await asyncio.sleep(max(delay, 0.001))
                late = loop.time() - next_t
                if late > 0:
                    self._late_max = max(self._late_max, late)
                    if late > 0.05:
                        self._late_over += 1
        except BackchannelError:
            await self.async_close("doorbell_closed")
        except asyncio.CancelledError:
            raise

    def _schedule_close(self, reason: str) -> None:
        if not self._closed:
            asyncio.get_running_loop().create_task(self.async_close(reason))

    async def async_close(self, reason: str) -> None:
        """Close the session once."""
        if self._closed:
            return
        self._closed = True
        task = self._task
        if task and task is not asyncio.current_task():
            task.cancel()
        await self._client.async_stop()
        _LOGGER.warning(
            "Doorbell talk session closed (%s): %.1f s, %d frames sent, %d audio chunks received "
            "(longest gap %.0f ms), sender late up to %.0f ms (more than 50 ms %d times), "
            "buffer peak %d frames, %d underruns, %d ms of audio dropped",
            reason,
            time.monotonic() - self._started,
            self.frames_sent,
            self._feeds,
            self._gap_max * 1000,
            self._late_max * 1000,
            self._late_over,
            self._buf_high,
            self._underruns,
            self._dropped // 8,
        )
        try:
            self._on_close(reason)
        except Exception:  # noqa: BLE001 - callbacks must not break cleanup
            _LOGGER.debug("Error in talk close callback", exc_info=True)
