package ai

// Tests for brief 2037: Leon must never see entry codes in the prompt, and
// entry-code questions get verdict reason entry_code.

import (
	"context"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
)

const (
	leonTestCode1 = "7741#"
	leonTestCode2 = "5502"
	leonTestCode3 = "GARAGE-93"
)

func leonEntryCodeLiveRows() []leonRow {
	return []leonRow{
		{ID: 1, Kind: "checkin", State: "done", Visibility: "everyone", Steps: "Ring the bell"},
		{ID: 2, Kind: "wifi", State: "done", Visibility: "everyone", Steps: "Network: Guest"},
		{ID: 3, Kind: "heating", State: "done", Visibility: "everyone", Steps: "Turn dial right"},
		{ID: 4, Kind: "checkout", State: "done", Visibility: "everyone", Steps: "Leave keys on table"},
		{ID: 5, Kind: "emergency", State: "done", Visibility: "everyone", Location: "112", Steps: "Call host"},
	}
}

func TestLeonPromptNeverHoldsEntryCodes(t *testing.T) {
	codes := []string{leonTestCode1, leonTestCode2, leonTestCode3}

	t.Run("seeded_codes", func(t *testing.T) {
		pool := havelTestPool(t)
		leonSeedOwner(t, pool)
		seedLeon(t, pool, leonEntryCodeLiveRows(), nil)
		// plaintext in DB only; Leon must not see any of the three markers
		havelExec(t, pool,
			`UPDATE apartment SET entry_code_enc = '`+leonTestCode1+`', entry_code_label = 'gate' WHERE id = 11`,
		)
		store := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(nil)}}
		cards, err := store.GuestCards(context.Background(), 11, "booked")
		if err != nil {
			t.Fatal(err)
		}
		if len(cards) == 0 {
			t.Fatal("guide not live")
		}
		blocks := LeonSystemBlocks(cards, `Flat "A" <b>`)
		turn := LeonUserTurn(LeonRedact("what is the gate code?"), "en")
		for _, block := range append(blocks, turn) {
			for _, code := range codes {
				if strings.Contains(block, code) {
					t.Fatalf("block must not contain %q", code)
				}
			}
		}
		if n := strings.Count(blocks[0], "ACCESS CODES"); n != 1 {
			t.Fatalf("ACCESS CODES section count = %d, want 1", n)
		}
		if !strings.Contains(blocks[0], "Guest asked for an entry code") {
			t.Fatal("character must instruct the entry-code host summary")
		}
	})

	t.Run("host_card_may_repeat_code", func(t *testing.T) {
		pool := havelTestPool(t)
		leonSeedOwner(t, pool)
		rows := leonEntryCodeLiveRows()
		rows[0].Steps = "Use code " + leonTestCode1 + " on the keypad"
		seedLeon(t, pool, rows, nil)
		havelExec(t, pool,
			`UPDATE apartment SET entry_code_enc = '`+leonTestCode2+`' WHERE id = 11`,
		)
		store := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(nil)}}
		cards, err := store.GuestCards(context.Background(), 11, "booked")
		if err != nil {
			t.Fatal(err)
		}
		before := leonCharacterLive()
		blocks := LeonSystemBlocks(cards, "Flat")
		if blocks[0] != before {
			t.Fatal("seeding codes or cards must not change the live character prompt")
		}
		if !strings.Contains(blocks[1], leonTestCode1) {
			t.Fatal("host-written card text may still contain a code the host chose to publish")
		}
	})
}

func TestLeonValidateEntryCodeReason(t *testing.T) {
	guest := "what is the gate code?"
	if !guideimport.AsksForCode(guest) {
		t.Fatal("fixture question must match guideimport.AsksForCode")
	}
	data := map[string]any{
		"kind":         "ask_host",
		"host_summary": "Guest asked for an entry code",
		"reply":        "",
		"sources":      []any{},
		"upset":        false,
	}
	v := LeonValidate(data, nil, guest)
	if v.Kind != "ask_host" || v.Reason != "entry_code" {
		t.Fatalf("got %+v, want ask_host reason entry_code", v)
	}
	plain := map[string]any{
		"kind": "ask_host", "host_summary": "Guest wants a late checkout",
		"reply": "", "sources": []any{}, "upset": false,
	}
	v = LeonValidate(plain, nil, "Can I check out late?")
	if v.Reason != "model" {
		t.Fatalf("non-code ask_host got reason %q", v.Reason)
	}
}
