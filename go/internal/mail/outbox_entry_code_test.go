package mail

import (
	"errors"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const entryCodeFernetKey = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

func entryCodeTestConfig(t *testing.T) Config {
	t.Helper()
	keys, err := secure.NewMultiFernet([]byte(entryCodeFernetKey))
	if err != nil {
		t.Fatal(err)
	}
	return Config{Keys: keys}
}

func entryCodeEnc(t *testing.T, keys *secure.MultiFernet, plain string) string {
	t.Helper()
	token, err := keys.EncryptString(plain)
	if err != nil {
		t.Fatal(err)
	}
	return token
}

func assertNoSecretsInErr(t *testing.T, err error, secrets ...string) {
	t.Helper()
	if err == nil {
		return
	}
	msg := err.Error()
	for _, s := range secrets {
		if s != "" && strings.Contains(msg, s) {
			t.Fatalf("error must not contain %q: %s", s, msg)
		}
	}
}

func TestWithEntryCodesTextReplacesMarker1(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	p := obPayload{EntryCodePayloadKey(1): entryCodeEnc(t, cfg.Keys, "A1#-*")}
	got, err := cfg.withEntryCodes("code: "+EntryCodeMarker1, p, false)
	if err != nil {
		t.Fatal(err)
	}
	want := "code: A1#-*"
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestWithEntryCodesHTMLEscapes(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	plain := `<b>&`
	p := obPayload{EntryCodePayloadKey(1): entryCodeEnc(t, cfg.Keys, plain)}
	got, err := cfg.withEntryCodes(EntryCodeMarker1, p, true)
	if err != nil {
		t.Fatal(err)
	}
	want := "&lt;b&gt;&amp;"
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestWithEntryCodesMarker2NoKey(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	body := "x " + EntryCodeMarker2
	for _, p := range []obPayload{
		{},
		{EntryCodePayloadKey(2): ""},
	} {
		_, err := cfg.withEntryCodes(body, p, false)
		if !errors.Is(err, ErrDecryption) {
			t.Fatalf("want ErrDecryption, got %v", err)
		}
		assertNoSecretsInErr(t, err)
	}
}

func TestWithEntryCodesKeysWithoutMarkersUnchanged(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	p := obPayload{
		EntryCodePayloadKey(1): entryCodeEnc(t, cfg.Keys, "one"),
		EntryCodePayloadKey(2): entryCodeEnc(t, cfg.Keys, "two"),
		EntryCodePayloadKey(3): entryCodeEnc(t, cfg.Keys, "three"),
	}
	body := "hello"
	got, err := cfg.withEntryCodes(body, p, false)
	if err != nil {
		t.Fatal(err)
	}
	if got != body {
		t.Fatalf("got %q want unchanged %q", got, body)
	}
}

func TestWithEntryCodesAllMarkersAndDoorCode(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	p := obPayload{
		doorCodeKey:            entryCodeEnc(t, cfg.Keys, "9999"),
		EntryCodePayloadKey(1): entryCodeEnc(t, cfg.Keys, "A1"),
		EntryCodePayloadKey(2): entryCodeEnc(t, cfg.Keys, "B2"),
		EntryCodePayloadKey(3): entryCodeEnc(t, cfg.Keys, "C3"),
	}
	body := DoorCodeMarker + " " + EntryCodeMarker1 + " " + EntryCodeMarker2 + " " + EntryCodeMarker3
	got, err := cfg.withDoorCode(body, p)
	if err != nil {
		t.Fatal(err)
	}
	got, err = cfg.withEntryCodes(got, p, false)
	if err != nil {
		t.Fatal(err)
	}
	want := "9999# A1 B2 C3"
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestWithEntryCodesNoCrossPositionFill(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	p := obPayload{EntryCodePayloadKey(2): entryCodeEnc(t, cfg.Keys, "only-two")}
	_, err := cfg.withEntryCodes(EntryCodeMarker1, p, false)
	if !errors.Is(err, ErrDecryption) {
		t.Fatalf("want ErrDecryption, got %v", err)
	}
	assertNoSecretsInErr(t, err, "only-two")
}

func TestEntryCodeMarkerAndPayloadKeyBounds(t *testing.T) {
	for _, pos := range []int{0, 4} {
		if EntryCodeMarker(pos) != "" {
			t.Fatalf("EntryCodeMarker(%d) = %q", pos, EntryCodeMarker(pos))
		}
	}
	if EntryCodePayloadKey(4) != "" {
		t.Fatalf("EntryCodePayloadKey(4) = %q", EntryCodePayloadKey(4))
	}
}

func TestWithEntryCodesGarbageCiphertext(t *testing.T) {
	cfg := entryCodeTestConfig(t)
	garbage := "not-a-valid-token"
	p := obPayload{EntryCodePayloadKey(1): garbage}
	_, err := cfg.withEntryCodes(EntryCodeMarker1, p, false)
	if !errors.Is(err, ErrDecryption) {
		t.Fatalf("want ErrDecryption, got %v", err)
	}
	if strings.Contains(err.Error(), garbage) {
		t.Fatalf("error must not echo ciphertext: %s", err)
	}
}
