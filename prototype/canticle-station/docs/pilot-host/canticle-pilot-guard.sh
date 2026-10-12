#!/bin/sh
# canticle-pilot-guard.sh: the canticle daemon's start check on a LAN pilot host (binary-canticle#103).
# Documented only; the host owner copies it to ~/.binary-canticle/ and pilot.conf runs it before every start.
#
# It refuses to start the daemon unless
#   1. CANTICLE_BIND is one exact IPv4 address and port (never 0.0.0.0, ::, a name or IPv6), and
#   2. table inet canticle is loaded and drops datagrams to that address and port from other interfaces and
#      other sources (canticle-pilot.nft), so the daemon never listens unscoped.
#
# Exit status: 0 go; 78 CANTICLE_BIND is wrong; 69 the table can't be read or isn't loaded; 65 the table is
# loaded but doesn't scope that address and port. Every refusal says why on stderr (the unit's journal).
#
# Reading the table needs root. As a seat user it runs `sudo -n nft list table inet canticle`, which needs a sudo
# rule that lets the seat run exactly that without a password (README.md, step 3), and a unit line without
# NoNewPrivileges: pilot.conf runs it as `ExecStartPre=+`.

set -u
PATH=$PATH:/usr/sbin:/sbin

refuse() {
	echo "canticle-pilot-guard: refusing to start the daemon: $2" >&2
	exit "$1"
}

bind=${CANTICLE_BIND-}
case $bind in
'')
	refuse 78 "CANTICLE_BIND is empty or unset: set it in ~/.binary-canticle/pilot.env to this host's LAN address and port" ;;
0.0.0.0 | 0.0.0.0:* | :: | :::* | '[::]' | '[::]:'* | \**)
	refuse 78 "CANTICLE_BIND=$bind listens on every address: set it to this host's exact LAN address and port" ;;
*\[* | *:*:*)
	refuse 78 "CANTICLE_BIND=$bind is IPv6: the daemon binds one IPv4 address and port" ;;
:*)
	refuse 78 "CANTICLE_BIND=$bind has no address, so it would listen on every address: write ADDRESS:PORT" ;;
*:*) ;;
*)
	refuse 78 "CANTICLE_BIND=$bind has no port: write ADDRESS:PORT, such as 10.0.0.100:9999" ;;
esac

addr=${bind%:*}
port=${bind##*:}
case $port in
'' | *[!0-9]* | 0* | ??????*)
	refuse 78 "CANTICLE_BIND=$bind: the port must be a number from 1 to 65535" ;;
esac
[ "$port" -le 65535 ] || refuse 78 "CANTICLE_BIND=$bind: the port must be a number from 1 to 65535"

case $addr in
'' | *[!0-9.]* | .* | *. | *..*)
	refuse 78 "CANTICLE_BIND=$bind: $addr is not an IPv4 address (four numbers 0-255, dot-separated)" ;;
esac
saved_ifs=$IFS
IFS=.
set -- $addr    # split on the dots; $addr holds only digits and dots, so nothing else expands
IFS=$saved_ifs
[ "$#" -eq 4 ] || refuse 78 "CANTICLE_BIND=$bind: $addr is not an IPv4 address (four numbers 0-255, dot-separated)"
for octet in "$@"; do
	case $octet in
	0?* | ????*) refuse 78 "CANTICLE_BIND=$bind: $addr is not an IPv4 address (no leading zeros)" ;;
	esac
	[ "$octet" -le 255 ] || refuse 78 "CANTICLE_BIND=$bind: $addr is not an IPv4 address (four numbers 0-255)"
done

if [ "$(id -u)" -eq 0 ]; then
	listing=$(nft list table inet canticle 2>&1)
	status=$?
else
	listing=$(sudo -n nft list table inet canticle 2>&1)
	status=$?
fi
if [ "$status" -ne 0 ]; then
	case $listing in
	*'No such file or directory'*)
		hint="table inet canticle is not loaded: sudo systemctl start canticle-nft.service" ;;
	*'no new privileges'*)
		hint="NoNewPrivileges stops sudo: run this guard as ExecStartPre=+ (pilot.conf does)" ;;
	*'password is required'* | *'not allowed'* | *'may not run sudo'*)
		hint="the seat user can't read the table without a password: add the sudo rule (README.md, step 3)" ;;
	*)
		hint="run sudo -n nft list table inet canticle to see why" ;;
	esac
	first=$(printf '%s\n' "$listing" | sed -n 1p)
	refuse 69 "can't read table inet canticle ($first): $hint"
fi

# The two drops as nft lists them, in one chain on the input hook, with no rule before them that could let a
# datagram past them (accept, return, jump, goto, queue):
#   chain in {
#     type filter hook input priority filter - 10; policy accept;
#     ip daddr ADDR udp dport PORT iifname != "IF" counter packets N bytes N drop
#     ip daddr ADDR udp dport PORT ip saddr != PEERS counter packets N bytes N drop
#   }
# Drops in a chain without the hook, or after such a rule, don't count: nothing would reach them.
if ! printf '%s\n' "$listing" | awk -v want="ip daddr $addr udp dport $port " '
	$1 == "chain" && $NF == "{" { chain = 1; hook = iif = src = passed = 0; next }
	!chain { next }
	$1 == "}" { if (hook && iif && src) ok = 1; chain = 0; next }
	$1 == "type" { hook = ($2 == "filter" && $3 == "hook" && $4 == "input"); next }
	{
		drop = pass = 0
		for (i = 1; i <= NF; i++) {
			if ($i == "drop") drop = 1
			if ($i == "accept" || $i == "return" || $i == "jump" || $i == "goto" || $i == "queue") pass = 1
		}
		if (pass && !(iif && src)) passed = 1
		if (drop && !pass && !passed && index($0, want)) {
			if (index($0, " iifname != ")) iif = 1
			if (index($0, " ip saddr != ")) src = 1
		}
	}
	END { exit !ok }
'; then
	refuse 65 "table inet canticle doesn't drop datagrams to $addr:$port from other interfaces and other sources, in its input chain and before any other verdict: load the kit's canticle-pilot.nft with LOCAL and PORT matching CANTICLE_BIND, then sudo systemctl reload canticle-nft.service"
fi

echo "canticle-pilot-guard: ok: bind $addr:$port; table inet canticle drops datagrams to it from other interfaces and other sources" >&2
exit 0
