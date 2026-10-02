"""Decode Linux ``struct tcp_info`` (include/uapi/linux/tcp.h) from getsockopt(TCP_INFO)."""

from __future__ import annotations

import socket
import struct

_FIELDS = (
    "state ca_state retransmits probes backoff options wscale app_limited "
    "rto ato snd_mss rcv_mss unacked sacked lost retrans fackets "
    "last_data_sent last_ack_sent last_data_recv last_ack_recv "
    "pmtu rcv_ssthresh rtt rttvar snd_ssthresh snd_cwnd advmss reordering rcv_rtt rcv_space total_retrans "
    "pacing_rate max_pacing_rate bytes_acked bytes_received segs_out segs_in "
    "notsent_bytes min_rtt data_segs_in data_segs_out delivery_rate "
    "busy_time rwnd_limited sndbuf_limited delivered delivered_ce bytes_sent bytes_retrans "
    "dsack_dups reord_seen rcv_ooopack snd_wnd"
).split()
_FMT = struct.Struct("=8B24I4Q2I4IQ3Q2I2Q4I")
assert len(_FIELDS) == len(_FMT.unpack(bytes(_FMT.size)))

TCP_STATES = {1: "ESTABLISHED", 2: "SYN_SENT", 3: "SYN_RECV", 4: "FIN_WAIT1", 5: "FIN_WAIT2", 6: "TIME_WAIT",
              7: "CLOSE", 8: "CLOSE_WAIT", 9: "LAST_ACK", 10: "LISTEN", 11: "CLOSING"}
CA_STATES = {0: "Open", 1: "Disorder", 2: "CWR", 3: "Recovery", 4: "Loss"}
TCP_NOTSENT_LOWAT = 25


def tcp_info(sock: socket.socket) -> dict:
    raw = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, _FMT.size)
    raw = raw.ljust(_FMT.size, b"\0")  # older kernels return a shorter struct
    return dict(zip(_FIELDS, _FMT.unpack(raw)))


def brief(sock: socket.socket) -> dict:
    """The fields that explain a stall: RTO (ms), backoff, consecutive retransmits, queues."""
    i = tcp_info(sock)
    return {"state": TCP_STATES.get(i["state"], i["state"]), "ca_state": CA_STATES.get(i["ca_state"], i["ca_state"]),
            "rto_ms": i["rto"] / 1000, "backoff": i["backoff"], "retransmits": i["retransmits"],
            "total_retrans": i["total_retrans"], "unacked": i["unacked"], "notsent_bytes": i["notsent_bytes"],
            "cwnd": i["snd_cwnd"], "srtt_us": i["rtt"], "rttvar_us": i["rttvar"], "bytes_retrans": i["bytes_retrans"]}
