"""Tests of the voice client against a fake RTSP doorbell (no Home Assistant needed).

Run with:  python tests/test_talk.py   (or pytest, if installed)
"""

import asyncio
import hashlib
import importlib.util
import pathlib
import re
import statistics
import struct
import sys

PKG = pathlib.Path(__file__).parent.parent / "custom_components" / "reolink_talk"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"rt_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


talk = _load("talk")

SDP = (
    "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=Test\r\nt=0 0\r\n"
    "m=video 0 RTP/AVP 96\r\na=control:track1\r\n"
    "m=audio 0 RTP/AVP 8\r\na=recvonly\r\na=control:track2\r\n"
    "m=audio 0 RTP/AVP 0\r\na={talk}\r\na=control:track3\r\n"
)


class FakeDoorbell:
    """Tiny RTSP server that behaves like the doorbell's ONVIF backchannel."""

    def __init__(
        self,
        user="admin",
        password="s3cret!",
        qop=True,
        noise_before_reply=False,
        talk_track=True,
        close_after_play=False,
    ):
        self.user, self.password, self.qop = user, password, qop
        self.noise_before_reply = noise_before_reply
        self.talk_track = talk_track
        self.close_after_play = close_after_play
        self.realm, self.nonce = "FakeDoorbell", "0123456789abcdef"
        self.methods: list[str] = []
        self.rtp: list[tuple[float, bytes]] = []
        self.teardown = False
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    def _digest_ok(self, method, auth):
        fields = dict(re.findall(r'(\w+)="?([^",]*)"?', auth))
        ha1 = hashlib.md5(f"{self.user}:{self.realm}:{self.password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{fields.get('uri', '')}".encode()).hexdigest()
        if self.qop:
            expect = hashlib.md5(
                f"{ha1}:{self.nonce}:{fields['nc']}:{fields['cnonce']}:auth:{ha2}".encode()
            ).hexdigest()
        else:
            expect = hashlib.md5(f"{ha1}:{self.nonce}:{ha2}".encode()).hexdigest()
        return fields.get("username") == self.user and fields.get("response") == expect

    def _reply(self, cseq, status="200 OK", headers=None, body=""):
        lines = [f"RTSP/1.0 {status}", f"CSeq: {cseq}"] + (headers or [])
        if body:
            lines += ["Content-Type: application/sdp", f"Content-Length: {len(body)}"]
        return ("\r\n".join(lines) + "\r\n\r\n" + body).encode()

    async def _handle(self, reader, writer):
        loop = asyncio.get_running_loop()
        try:
            while True:
                first = await reader.readexactly(1)
                if first == b"$":  # interleaved RTP from the client
                    head = await reader.readexactly(3)
                    payload = await reader.readexactly(int.from_bytes(head[1:3], "big"))
                    self.rtp.append((loop.time(), payload))
                    continue
                raw = first + await reader.readuntil(b"\r\n\r\n")
                text = raw.decode()
                lines = text.split("\r\n")
                method, url, _ = lines[0].split(" ", 2)
                hdr = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:] if ":" in l)}
                cseq = hdr.get("cseq", "0")
                self.methods.append(method)
                if self.noise_before_reply:
                    rtcp = b"\x80\xc8 \x00\x06 sender report"  # contains spaces, like a real RTCP packet
                    writer.write(b"$\x01" + struct.pack(">H", len(rtcp)) + rtcp)
                if method == "TEARDOWN":
                    self.teardown = True
                    writer.write(self._reply(cseq))
                    await writer.drain()
                    continue
                if "authorization" not in hdr or not self._digest_ok(method, hdr["authorization"]):
                    www = f'WWW-Authenticate: Digest realm="{self.realm}", nonce="{self.nonce}"'
                    if self.qop:
                        www += ', qop="auth"'
                    writer.write(self._reply(cseq, "401 Unauthorized", [www]))
                elif method == "DESCRIBE":
                    sdp = SDP.format(talk="sendonly" if self.talk_track else "recvonly")
                    writer.write(
                        self._reply(cseq, headers=[f"Content-Base: rtsp://127.0.0.1:{self.port}/h264Preview_01_sub/"], body=sdp)
                    )
                elif method == "SETUP":
                    writer.write(
                        self._reply(
                            cseq,
                            headers=["Session: 12345678;timeout=60", "Transport: RTP/AVP/TCP;unicast;interleaved=0-1"],
                        )
                    )
                elif method == "PLAY":
                    writer.write(self._reply(cseq))
                    await writer.drain()
                    if self.close_after_play:
                        writer.close()
                        return
                else:
                    writer.write(self._reply(cseq, "405 Method Not Allowed"))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


def _run(coro):
    return asyncio.run(asyncio.wait_for(coro, 30))


def _client(server, password=None):
    return talk.BackchannelClient(
        "127.0.0.1", server.user, password or server.password, port=server.port
    )


def _parse_rtp(packet):
    b0, b1, seq, ts, ssrc = struct.unpack(">BBHII", packet[:12])
    return {"version": b0 >> 6, "pt": b1 & 0x7F, "seq": seq, "ts": ts, "ssrc": ssrc, "payload": packet[12:]}


# ---- client ----------------------------------------------------------------
def test_open_with_digest_qop_and_send_frames():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        client = _client(srv)
        await client.async_start()
        assert srv.methods == ["DESCRIBE", "DESCRIBE", "SETUP", "PLAY"]
        for i in range(5):
            client.send_frame(bytes([i]) * 160)
        await asyncio.sleep(0.2)
        pkts = [_parse_rtp(p) for _, p in srv.rtp]
        assert len(pkts) == 5
        assert all(p["version"] == 2 and p["pt"] == 0 and len(p["payload"]) == 160 for p in pkts)
        assert [p["seq"] for p in pkts] == [(pkts[0]["seq"] + i) & 0xFFFF for i in range(5)]
        assert [p["ts"] for p in pkts] == [(pkts[0]["ts"] + 160 * i) & 0xFFFFFFFF for i in range(5)]
        assert len({p["ssrc"] for p in pkts}) == 1
        await client.async_stop()
        await asyncio.sleep(0.1)
        assert srv.teardown
        await srv.stop()

    _run(go())


def test_open_with_digest_without_qop():
    async def go():
        srv = FakeDoorbell(qop=False)
        await srv.start()
        client = _client(srv)
        await client.async_start()
        await client.async_stop()
        await srv.stop()

    _run(go())


def test_interleaved_frame_before_reply_is_skipped():
    """Regression: the doorbell sometimes sends a '$' frame before the RTSP reply."""

    async def go():
        srv = FakeDoorbell(noise_before_reply=True)
        await srv.start()
        client = _client(srv)
        await client.async_start()
        await client.async_stop()
        await srv.stop()

    for _ in range(3):
        _run(go())


def test_wrong_password_is_invalid_auth():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        client = _client(srv, password="not-the-password")
        try:
            await client.async_start()
        except talk.BackchannelError as err:
            assert str(err) == "invalid_auth"
        else:
            raise AssertionError("expected BackchannelError")
        await srv.stop()

    _run(go())


def test_no_talk_track():
    async def go():
        srv = FakeDoorbell(talk_track=False)
        await srv.start()
        client = _client(srv)
        try:
            await client.async_start()
        except talk.BackchannelError as err:
            assert str(err) == "no_talk_track"
        else:
            raise AssertionError("expected BackchannelError")
        await srv.stop()

    _run(go())


def test_connection_refused_is_a_clean_error():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        port = srv.port
        await srv.stop()  # nothing listens on this port any more
        client = talk.BackchannelClient("127.0.0.1", "u", "p", port=port)
        try:
            await client.async_start()
        except talk.BackchannelError as err:
            assert str(err).startswith("connection")
        else:
            raise AssertionError("expected BackchannelError")

    _run(go())


def test_find_talk_control_picks_the_sendonly_audio_track():
    sdp = SDP.format(talk="sendonly")
    assert talk.BackchannelClient._find_talk_control(sdp) == "track3"


# ---- session ---------------------------------------------------------------
def test_buffer_never_holds_more_than_the_cap():
    client = talk.BackchannelClient("127.0.0.1", "u", "p")
    session = talk.TalkSession(client, lambda reason: None)
    session.feed(b"\x7f" * 8000)  # 50 frames at once
    assert len(session._buf) == talk.MAX_BUFFER_FRAMES * talk.FRAME_BYTES
    assert session._dropped == 8000 - talk.MAX_BUFFER_FRAMES * talk.FRAME_BYTES


def test_session_paces_frames_every_20_ms():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        reasons = []
        session = talk.TalkSession(_client(srv), reasons.append)
        await session.async_start()
        # The browser sends 60 ms chunks in real time.
        for _ in range(20):
            session.feed(b"\x7f" * (talk.FRAME_BYTES * 3))
            await asyncio.sleep(0.06)
        await asyncio.sleep(0.2)
        times = [t for t, _ in srv.rtp]
        assert len(times) >= 40, len(times)
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert 0.012 < statistics.median(gaps) < 0.028, statistics.median(gaps)
        await session.async_close("client")
        assert reasons == ["client"]
        await srv.stop()

    _run(go())


def test_session_closes_on_idle():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        reasons = []
        session = talk.TalkSession(_client(srv), reasons.append, idle_seconds=1)
        await session.async_start()
        await asyncio.sleep(2)
        assert reasons == ["idle"]
        assert srv.teardown
        await srv.stop()

    _run(go())


def test_session_closes_at_max_time():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        reasons = []
        session = talk.TalkSession(_client(srv), reasons.append, max_seconds=1, idle_seconds=30)
        await session.async_start()
        for _ in range(15):
            session.feed(b"\x7f" * talk.FRAME_BYTES * 3)
            await asyncio.sleep(0.1)
        assert reasons == ["max_time"]
        await srv.stop()

    _run(go())


def test_session_reports_when_the_doorbell_hangs_up():
    async def go():
        srv = FakeDoorbell(close_after_play=True)
        await srv.start()
        reasons = []
        session = talk.TalkSession(_client(srv), reasons.append)
        await session.async_start()
        await asyncio.sleep(0.5)
        assert reasons == ["doorbell_closed"]
        await srv.stop()

    _run(go())


def test_close_is_idempotent():
    async def go():
        srv = FakeDoorbell()
        await srv.start()
        reasons = []
        session = talk.TalkSession(_client(srv), reasons.append)
        await session.async_start()
        await session.async_close("client")
        await session.async_close("client")
        assert reasons == ["client"]
        await srv.stop()

    _run(go())


if __name__ == "__main__":
    failed = 0
    for _name in sorted(n for n in dir() if n.startswith("test_")):
        try:
            globals()[_name]()
            print("ok", _name)
        except Exception as err:  # noqa: BLE001
            failed += 1
            print("FAIL", _name, repr(err))
    sys.exit(1 if failed else 0)
