// Package clientip names the visitor behind the reverse proxy exactly as
// App/app/client_ip.py and rate_limit.client_key do (brief 1501).
//
// The peer is the TCP address the request came from (r.RemoteAddr). Its
// CF-Connecting-IP header is believed only when that peer is inside one of
// the networks in UBYHOST_TRUSTED_PROXY_CIDRS; an unset value trusts nobody,
// so every visitor shares the proxy's address. It is a library only: no
// route is registered here.
package clientip

import (
	"net"
	"net/http"
	"net/netip"
	"strings"
)

// Unidentified is rate_limit.UNIDENTIFIED_CLIENT: the shared bucket for a
// request without a peer address.
const Unidentified = "unknown"

// header is the visitor address Cloudflare sets and Caddy passes on.
const header = "CF-Connecting-IP"

// TrustedNetworks is client_ip.trusted_proxy_networks: the comma-separated
// UBYHOST_TRUSTED_PROXY_CIDRS, each entry stripped, empty entries skipped, a
// bare address read as a one-address network and host bits ignored
// (ip_network(strict=False)). Python raises on an entry it cannot read and
// every request then fails; Go trusts nobody instead (ok is false).
func TrustedNetworks(getenv func(string) string) (nets []netip.Prefix, ok bool) {
	for _, part := range strings.Split(strings.TrimSpace(getenv("UBYHOST_TRUSTED_PROXY_CIDRS")), ",") {
		piece := strings.TrimSpace(part)
		if piece == "" {
			continue
		}
		if !strings.Contains(piece, "/") {
			addr, err := netip.ParseAddr(piece)
			if err != nil || addr.Zone() != "" {
				return nil, false
			}
			nets = append(nets, netip.PrefixFrom(addr, addr.BitLen()))
			continue
		}
		prefix, err := netip.ParsePrefix(piece)
		if err != nil {
			return nil, false
		}
		nets = append(nets, prefix.Masked())
	}
	return nets, true
}

// peerHost is client_ip.peer_host: the host part of RemoteAddr, "" when
// there is none.
func peerHost(r *http.Request) string {
	if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil {
		return host
	}
	return r.RemoteAddr
}

// trusted is client_ip.is_trusted_proxy. An IPv4-mapped IPv6 peer does not
// match an IPv4 network, as in Python.
func trusted(host string, nets []netip.Prefix) bool {
	if host == "" || len(nets) == 0 {
		return false
	}
	addr, err := netip.ParseAddr(host)
	if err != nil {
		return false
	}
	for _, n := range nets {
		if n.Contains(addr) {
			return true
		}
	}
	return false
}

// visitor is client_ip._normalise_visitor_ip: the stripped header as a
// canonical address, "" when it is not one.
func visitor(value string) string {
	addr, err := netip.ParseAddr(strings.TrimSpace(value))
	if err != nil {
		return ""
	}
	return addr.String()
}

// Host is request.client.host after client_ip.apply_visitor_client: the
// CF-Connecting-IP address when the peer is a trusted proxy and the header
// is a valid address, else the peer host; "" when there is no peer. This is
// the remoteip Turnstile receives.
func Host(r *http.Request, getenv func(string) string) string {
	peer := peerHost(r)
	nets, ok := TrustedNetworks(getenv)
	if ok && trusted(peer, nets) {
		if v := visitor(r.Header.Get(header)); v != "" {
			return v
		}
	}
	return peer
}

// Key is rate_limit.client_key(request, suffix): Host, or Unidentified when
// there is no peer, then ":" and suffix when suffix is not empty. It is never
// empty, so session.RateBlocked never fails closed on it.
func Key(r *http.Request, getenv func(string) string, suffix string) string {
	host := Host(r, getenv)
	if host == "" {
		host = Unidentified
	}
	if suffix != "" {
		return host + ":" + suffix
	}
	return host
}
