from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable

from .codec import MAX_PACKET_SIZE
from .model import Receipt
from .receptor import NoticeReceptor


class UdpCueListener:
    def __init__(
        self,
        receptor: NoticeReceptor,
        *,
        host: str = "127.0.0.1",
        port: int = 9999,
    ):
        address = ipaddress.ip_address(host)
        if address.version != 4 or not address.is_loopback:
            raise ValueError("listener_must_be_ipv4_loopback")
        self._receptor = receptor
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((host, port))

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._socket.getsockname()
        return str(host), int(port)

    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> UdpCueListener:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def receive_once(self, *, timeout: float | None = None) -> Receipt:
        self._socket.settimeout(timeout)
        packet, _peer = self._socket.recvfrom(MAX_PACKET_SIZE + 1)
        return self._receptor.process(packet)

    def serve_forever(
        self,
        *,
        on_receipt: Callable[[Receipt], None] | None = None,
    ) -> None:
        while True:
            receipt = self.receive_once()
            if on_receipt is not None:
                on_receipt(receipt)
