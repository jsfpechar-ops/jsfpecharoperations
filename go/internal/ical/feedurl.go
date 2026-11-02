// Package ical ports the iCal feed download from the Python app
// (App/app/feed_url.py and App/app/feed_fetch.py) to Go. The URL guard here
// refuses everything the Python guard refuses: a host's feed URL is user input,
// so this is a security boundary. Nothing calls this package yet.
package ical

import (
	"context"
	"net"
	"net/netip"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
)

// Translation keys the host UI flashes; the sync log keeps the English Msg.
const (
	keyURLMalformed  = "flash.error.feed_url_malformed"
	keyURLScheme     = "flash.error.feed_url_scheme"
	keyURLNoHost     = "flash.error.feed_url_no_host"
	keyURLCredential = "flash.error.feed_url_credentials"
	keyURLPort       = "flash.error.feed_url_port"
	keyURLHost       = "flash.error.feed_url_host"
	keyHostBlocked   = "flash.error.feed_host_blocked"
	keyHostPrivate   = "flash.error.feed_host_private"
	keyHostUnknown   = "flash.error.feed_host_unresolved"
	keyRedirectHTTP  = "flash.error.feed_redirect_insecure"
)

// FeedURLError is an unsafe or invalid calendar URL. Key is the host-facing
// translation key; Msg is the English wording (what the sync log records).
type FeedURLError struct {
	Msg string
	Key string
}

func (e *FeedURLError) Error() string { return e.Msg }

// Resolver is the DNS lookup used once per hop. net.DefaultResolver fits.
type Resolver interface {
	LookupNetIP(ctx context.Context, network, host string) ([]netip.Addr, error)
}

// Target is a validated URL plus the addresses the next connect may use.
type Target struct {
	URL    string
	Host   string
	Port   int
	Scheme string
	IPs    []netip.Addr
}

var blockedHostnames = map[string]bool{
	"localhost":                true,
	"metadata.google.internal": true,
	"metadata.google":          true,
}

// Ranges Python's ipaddress does not flag as private or reserved, but which
// still reach somewhere other than the public internet.
var extraBlockedV4 = mustPrefixes("100.64.0.0/10", "192.0.0.0/24", "198.18.0.0/15")

// Python ipaddress IPv4 _private_networks, minus its exceptions.
var privateV4 = mustPrefixes(
	"0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
	"192.0.0.0/24", "192.0.0.170/31", "192.0.2.0/24", "192.168.0.0/16",
	"198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "240.0.0.0/4",
	"255.255.255.255/32",
)
var privateV4Exceptions = mustPrefixes("192.0.0.9/32", "192.0.0.10/32")

// Python ipaddress IPv6 _private_networks, minus its exceptions.
var privateV6 = mustPrefixes(
	"::1/128", "::/128", "::ffff:0:0/96", "64:ff9b:1::/48", "100::/64",
	"2001::/23", "2001:db8::/32", "2002::/16", "3fff::/20", "fc00::/7", "fe80::/10",
)
var privateV6Exceptions = mustPrefixes(
	"2001:1::1/128", "2001:1::2/128", "2001:3::/32", "2001:4:112::/48",
	"2001:20::/28", "2001:30::/28",
)

// Python ipaddress IPv6 _reserved_networks (is_reserved).
var reservedV6 = mustPrefixes(
	"::/8", "100::/8", "200::/7", "400::/6", "800::/5", "1000::/4",
	"4000::/3", "6000::/3", "8000::/3", "a000::/3", "c000::/3", "e000::/4",
	"f000::/5", "f800::/6", "fe00::/9",
)

// Python's is_reserved for IPv4 is 240.0.0.0/4, already inside privateV4.

var canonicalNumericHost = regexp.MustCompile(`^[0-9a-fA-FxX.]+$`)

func mustPrefixes(cidrs ...string) []netip.Prefix {
	out := make([]netip.Prefix, 0, len(cidrs))
	for _, c := range cidrs {
		out = append(out, netip.MustParsePrefix(c))
	}
	return out
}

func inAny(prefixes []netip.Prefix, ip netip.Addr) bool {
	for _, p := range prefixes {
		if p.Contains(ip) {
			return true
		}
	}
	return false
}

// blockedIP mirrors Python's _blocked_ip. Every IPv4-mapped IPv6 address is
// refused, as Python does (::ffff:0:0/96 is in its private list), so the
// embedded IPv4 is never reached through a mapped form.
func blockedIP(ip netip.Addr) bool {
	if ip.Is4In6() {
		return true
	}
	if ip.Is4() {
		if inAny(privateV4, ip) && !inAny(privateV4Exceptions, ip) {
			return true
		}
		return inAny(extraBlockedV4, ip) || ip.IsMulticast()
	}
	if inAny(privateV6, ip) && !inAny(privateV6Exceptions, ip) {
		return true
	}
	if inAny(reservedV6, ip) {
		return true
	}
	return ip.IsLoopback() || ip.IsUnspecified() || ip.IsMulticast() || ip.IsLinkLocalUnicast()
}

// ambiguousNumericHost is true when resolvers and HTTP clients could read the
// host differently (0177.0.0.1, 2130706433, 0x7f.1, 127.1). Only canonical
// literals are unambiguous.
func ambiguousNumericHost(host string) bool {
	if !canonicalNumericHost.MatchString(host) {
		return false
	}
	addr, err := netip.ParseAddr(host)
	if err != nil {
		return true
	}
	if addr.Is4() {
		return host != addr.String()
	}
	return false
}

// AllowPrivate reports whether private targets are allowed: the env flag
// UBYHOST_ICAL_ALLOW_PRIVATE is truthy and UBYHOST_DEPLOYMENT is not production.
func AllowPrivate(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_ICAL_ALLOW_PRIVATE")) {
	case "1", "true", "yes":
	default:
		return false
	}
	deployment := strings.ToLower(getenv("UBYHOST_DEPLOYMENT"))
	if deployment == "" {
		deployment = "local"
	}
	return deployment != "production"
}

// AllowPrivateFromEnv is AllowPrivate reading the process environment.
func AllowPrivateFromEnv() bool { return AllowPrivate(os.Getenv) }

func feedErr(msg, key string) error {
	return &FeedURLError{Msg: msg, Key: key}
}

// ResolveTarget validates a calendar URL, resolves its host once, and returns
// the addresses the connect may pin to.
func ResolveTarget(ctx context.Context, rawURL string, r Resolver, allowPrivate bool) (Target, error) {
	raw := strings.TrimSpace(rawURL)
	u, err := url.Parse(raw)
	if err != nil {
		return Target{}, feedErr("Calendar URL is malformed.", keyURLMalformed)
	}
	port := 0
	if p := u.Port(); p != "" {
		n, perr := strconv.Atoi(p)
		if perr != nil || n > 65535 {
			return Target{}, feedErr("Calendar URL is malformed.", keyURLMalformed)
		}
		port = n
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return Target{}, feedErr("Calendar URL must use http:// or https://.", keyURLScheme)
	}
	hostname := u.Hostname()
	if hostname == "" {
		return Target{}, feedErr("Calendar URL is missing a hostname.", keyURLNoHost)
	}
	if u.User != nil {
		return Target{}, feedErr("Calendar URL must not contain embedded credentials.", keyURLCredential)
	}
	if u.Port() != "" && (port < 1 || port > 65535) {
		return Target{}, feedErr("Calendar URL has an invalid port.", keyURLPort)
	}
	host := strings.TrimRight(strings.ToLower(hostname), ".")
	if !allowPrivate {
		if ambiguousNumericHost(host) {
			return Target{}, feedErr("Calendar URL must use a canonical IP address or a public hostname.", keyURLHost)
		}
		if blockedHostnames[host] || strings.HasSuffix(host, ".local") {
			return Target{}, feedErr("That calendar host is not allowed.", keyHostBlocked)
		}
		if host == "127.0.0.1" || strings.HasPrefix(host, "127.") {
			return Target{}, feedErr("Calendar URL must not point to a loopback address.", keyHostBlocked)
		}
	}
	ips, err := resolveHost(ctx, host, r)
	if err != nil {
		return Target{}, err
	}
	if !allowPrivate {
		for _, ip := range ips {
			if blockedIP(ip) {
				return Target{}, feedErr(
					"Calendar URL must point to a public internet host, not a private or internal address.",
					keyHostPrivate)
			}
		}
	}
	seen := make(map[netip.Addr]bool, len(ips))
	pinned := make([]netip.Addr, 0, len(ips))
	for _, ip := range ips {
		if !seen[ip] {
			seen[ip] = true
			pinned = append(pinned, ip)
		}
	}
	if port == 0 {
		port = 80
		if u.Scheme == "https" {
			port = 443
		}
	}
	return Target{URL: raw, Host: host, Port: port, Scheme: u.Scheme, IPs: pinned}, nil
}

func resolveHost(ctx context.Context, host string, r Resolver) ([]netip.Addr, error) {
	if addr, err := netip.ParseAddr(host); err == nil {
		return []netip.Addr{addr}, nil
	}
	if r == nil {
		r = net.DefaultResolver
	}
	addrs, err := r.LookupNetIP(ctx, "ip", host)
	if err != nil {
		return nil, feedErr("Could not resolve calendar host: "+err.Error(), keyHostUnknown)
	}
	if len(addrs) == 0 {
		return nil, feedErr("Could not resolve calendar host.", keyHostUnknown)
	}
	return addrs, nil
}

// ResolveRedirect joins a Location header onto the current URL and validates
// the result again. An https feed may not redirect to http.
func ResolveRedirect(ctx context.Context, current, location string, r Resolver, allowPrivate bool) (Target, error) {
	base, err := url.Parse(current)
	if err != nil {
		return Target{}, feedErr("Calendar URL is malformed.", keyURLMalformed)
	}
	ref, err := url.Parse(location)
	if err != nil {
		return Target{}, feedErr("Calendar URL is malformed.", keyURLMalformed)
	}
	joined := base.ResolveReference(ref).String()
	if schemeOf(current) == "https" && schemeOf(joined) != "https" {
		return Target{}, feedErr(
			"Calendar redirect would drop HTTPS, which would let the feed be tampered with "+
				"in transit. Point the feed at the address it redirects to.",
			keyRedirectHTTP)
	}
	return ResolveTarget(ctx, joined, r, allowPrivate)
}

func schemeOf(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	return u.Scheme
}
