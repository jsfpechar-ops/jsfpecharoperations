package ubyport

// Tests of the read-only calls (brief 1702d2). The envelopes are what
// App/app/ubyport/soap.py build_simple_call and build_dej_mi_ciselnik return,
// written out by hand; no test reaches the network (httptest only).

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"testing"
)

func TestReadOnlyEnvelopesMatchPython(t *testing.T) {
	for _, c := range []struct{ got, want string }{
		{BuildSimpleCall("TestDostupnosti", "X", "", false),
			`<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header></s:Header><s:Body><TestDostupnosti xmlns="http://UBY.pcr.cz/WS_UBY"><AutentificationCode>X</AutentificationCode></TestDostupnosti></s:Body></s:Envelope>`},
		{BuildSimpleCall("MaximalniDelkaSeznamu", "X", "", true),
			`<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header><Action s:mustUnderstand="1" xmlns="http://schemas.microsoft.com/ws/2005/05/addressing/none">http://UBY.pcr.cz/WS_UBY/IWS_UBY/MaximalniDelkaSeznamu</Action></s:Header><s:Body><MaximalniDelkaSeznamu xmlns="http://UBY.pcr.cz/WS_UBY"><AutentificationCode>X</AutentificationCode></MaximalniDelkaSeznamu></s:Body></s:Envelope>`},
		{BuildDejMiCiselnik("Chyby", "X", false),
			`<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header></s:Header><s:Body><DejMiCiselnik xmlns="http://UBY.pcr.cz/WS_UBY"><AutentificationCode>X</AutentificationCode><CoChci>Chyby</CoChci></DejMiCiselnik></s:Body></s:Envelope>`},
		{BuildDejMiCiselnik("A<&>", "X", true),
			`<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header><Action s:mustUnderstand="1" xmlns="http://schemas.microsoft.com/ws/2005/05/addressing/none">http://UBY.pcr.cz/WS_UBY/IWS_UBY/DejMiCiselnik</Action></s:Header><s:Body><DejMiCiselnik xmlns="http://UBY.pcr.cz/WS_UBY"><AutentificationCode>X</AutentificationCode><CoChci>A&lt;&amp;&gt;</CoChci></DejMiCiselnik></s:Body></s:Envelope>`},
	} {
		if c.got != c.want {
			t.Errorf("envelope:\n got %s\nwant %s", c.got, c.want)
		}
	}
}

const readOnlyCiselnik = `<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><DejMiCiselnikResponse xmlns="http://UBY.pcr.cz/WS_UBY"><DejMiCiselnikResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY">` +
	`<a:CiselnikType><a:Kod2>ERR_CZE_112</a:Kod2><a:Kod3> Chybné datum </a:Kod3><a:TextKratkyCZ>2</a:TextKratkyCZ></a:CiselnikType>` +
	`<a:CiselnikType><a:Kod3>0114</a:Kod3><a:TextCZ>short</a:TextCZ><a:TextENG>a longer one</a:TextENG></a:CiselnikType>` +
	`</DejMiCiselnikResult></DejMiCiselnikResponse></s:Body></s:Envelope>`

func readOnlyScalar(method, value string) string {
	return `<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><` + method + `Response xmlns="http://UBY.pcr.cz/WS_UBY"><` +
		method + `Result>` + value + `</` + method + `Result></` + method + `Response></s:Body></s:Envelope>`
}

// TestReadOnlyCallsSendTheirAction: each call posts its own SOAPAction and
// envelope to the client's endpoint and reads the answer as Python does.
func TestReadOnlyCallsSendTheirAction(t *testing.T) {
	var mu sync.Mutex
	var actions, bodies []string
	limit := " 120 "
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		action := r.Header.Get("SOAPAction")
		mu.Lock()
		actions = append(actions, action)
		bodies = append(bodies, string(body))
		mu.Unlock()
		switch strings.TrimPrefix(action, ActionPrefix) {
		case "TestDostupnosti":
			_, _ = io.WriteString(w, readOnlyScalar("TestDostupnosti", " True "))
		case "MaximalniDelkaSeznamu":
			_, _ = io.WriteString(w, readOnlyScalar("MaximalniDelkaSeznamu", limit))
		default:
			_, _ = io.WriteString(w, readOnlyCiselnik)
		}
	}))
	defer srv.Close()
	c := NewClient(srv.URL+"/ws_uby/ws_uby.svc", "UBY-WS_TEST", "pw", "", "X", false, true)
	ctx := context.Background()
	if ok, err := c.TestAvailability(ctx); err != nil || !ok {
		t.Fatalf("TestAvailability: %v %v", ok, err)
	}
	if n, err := c.MaxBatchSize(ctx); err != nil || n == nil || *n != 120 {
		t.Fatalf("MaxBatchSize: %v %v", n, err)
	}
	rows, err := c.CodeList(ctx, CodeListErrors)
	if err != nil {
		t.Fatal(err)
	}
	want := []map[string]string{
		{"Kod2": "ERR_CZE_112", "Kod3": "Chybné datum", "TextKratkyCZ": "2"},
		{"Kod3": "0114", "TextCZ": "short", "TextENG": "a longer one"},
	}
	if !reflect.DeepEqual(rows, want) {
		t.Errorf("CodeList: %v", rows)
	}
	wantActions := []string{ActionPrefix + "TestDostupnosti", ActionPrefix + "MaximalniDelkaSeznamu", ActionPrefix + "DejMiCiselnik"}
	if !reflect.DeepEqual(actions, wantActions) {
		t.Errorf("actions: %v", actions)
	}
	wsa := wsaHeaderOn()
	wantBodies := []string{BuildSimpleCall("TestDostupnosti", "X", "", wsa), BuildSimpleCall("MaximalniDelkaSeznamu", "X", "", wsa), BuildDejMiCiselnik("Chyby", "X", wsa)}
	if !reflect.DeepEqual(bodies, wantBodies) {
		t.Errorf("bodies: %v", bodies)
	}
	for _, v := range []string{"", "many", "12.5"} {
		limit = v
		if n, err := c.MaxBatchSize(ctx); err != nil || n != nil {
			t.Errorf("MaxBatchSize of %q: %v %v, want nil", v, n, err)
		}
	}
}

func TestReadOnlyCallsKeepTheErrorKinds(t *testing.T) {
	c := NewClient(fixedServer(t, http.StatusUnauthorized, "").URL, "u", "p", "", "X", false, true)
	_, err := c.TestAvailability(context.Background())
	wantKind(t, err, ErrAuth)
	c = NewClient(fixedServer(t, http.StatusOK, readOnlyScalar("TestDostupnosti", "false")).URL, "u", "p", "", "X", false, true)
	if ok, err := c.TestAvailability(context.Background()); err != nil || ok {
		t.Errorf("false answer: %v %v", ok, err)
	}
	if _, err := c.CodeList(context.Background(), CodeListErrors); err != nil {
		t.Errorf("no CiselnikType: %v", err)
	}
}

// TestStoreErrorCodelist: codelists.store(KIND_ERRORS, rows), expected rows
// written by hand from codelists._code_and_texts and _extra.
func TestStoreErrorCodelist(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO codelist (kind, code, text_cs, text_en, extra, fetched_at) VALUES
  ('chyby', 'OLD', 'old', 'old', '', 'then'), ('staty', 'CZE', 'Česko', 'Czechia', 'CZ', 'then')`); err != nil {
		t.Fatal(err)
	}
	rows := []map[string]string{
		{"Kod2": "ERR_CZE_112", "Kod3": "Chybné datum", "TextKratkyCZ": "2", "TextENG": "Error"},
		{"Kod2": " err_cze_7 ", "Kod3": "", "TextCZ": "Text CZ", "TextKratkyCZ": "12"},
		{"Kod3": "0114", "TextCZ": "short", "TextENG": "a longer one", "TextKratkyCZ": "x"},
		{"TextCZ": "no code here"},
		{"Kod2": "ERR_CZE_112", "Kod3": "Jiný text", "TextKratkyCZ": ""},
		{"Kod2": "ERR_CZE_9", "Kod3": "", "TextCZ": "", "TextKratkyCZ": "3"},
	}
	n, err := StoreErrorCodelist(ctx, pool, rows, "2026-11-17T10:00:00+00:00")
	if err != nil || n != 5 {
		t.Fatalf("StoreErrorCodelist: %d %v, want 5", n, err)
	}
	got, err := pool.Query(ctx, `SELECT kind, code, text_cs, text_en, extra, fetched_at FROM codelist ORDER BY kind COLLATE "C", code COLLATE "C"`)
	if err != nil {
		t.Fatal(err)
	}
	defer got.Close()
	var lines []string
	for got.Next() {
		var k, c, cs, en, ex, at string
		if err := got.Scan(&k, &c, &cs, &en, &ex, &at); err != nil {
			t.Fatal(err)
		}
		lines = append(lines, strings.Join([]string{k, c, cs, en, ex, at}, "|"))
	}
	want := []string{
		"chyby|0114|a longer one|a longer one||2026-11-17T10:00:00+00:00",
		"chyby|ERR_CZE_112|Jiný text|Jiný text||2026-11-17T10:00:00+00:00",
		"chyby|ERR_CZE_9|||3|2026-11-17T10:00:00+00:00",
		"chyby|err_cze_7|Text CZ|Text CZ||2026-11-17T10:00:00+00:00",
		"staty|CZE|Česko|Czechia|CZ|then",
	}
	if !reflect.DeepEqual(lines, want) {
		t.Errorf("codelist:\n got %q\nwant %q", lines, want)
	}
}
