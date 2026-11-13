package billingjob

import "testing"

// pythonSnapshot is json.dumps({"invoice": inv, "items": rows}, ensure_ascii=False,
// sort_keys=True) for the values below, written by the real Python.
const pythonSnapshot = "{\"invoice\": {\"buyer_city\": \"C\", \"buyer_dic\": \"\", \"buyer_ico\": \"\", \"buyer_name\": \"Řád\\tx\", \"buyer_street\": \"S\", \"buyer_zip\": \"11000\", \"correction_reason\": \"x\\ny\\u0001\", \"corrects_number\": \"\", \"due_date\": \"2026-11-15\", \"issue_date\": \"2026-11-01\", \"kind\": \"invoice\", \"note\": \"Období: 01.11.2026 – 30.11.2026\", \"number\": \"UBY-2026-0042\", \"seller_bank_account\": \"19/0800\", \"seller_dic\": \"CZ1\", \"seller_email\": \"a@b.test\", \"seller_iban\": \"CZ65\", \"seller_ico\": \"1\", \"seller_name\": \"UbyHost \\\"s.r.o.\\\" <&>\", \"seller_seat\": \"Dlouhá 1\\\\\", \"total_haler\": -15000, \"vat_status\": \"non_payer\", \"vs\": \"20260042\"}, \"items\": [{\"description\": \"Předplatné\", \"gross_haler\": 14900, \"quantity\": 1}, {\"description\": \"Sleva\", \"gross_haler\": -1500, \"quantity\": 1}]}"

func TestSnapshotJSONMatchesPython(t *testing.T) {
	inv := invoiceDoc{
		seller: seller{
			Name: "UbyHost \"s.r.o.\" <&>", Seat: "Dlouhá 1\\", ICO: "1", DIC: "CZ1",
			Email: "a@b.test", IBAN: "CZ65", BankAccount: "19/0800", VATStatus: "non_payer",
		},
		buyer: account{BuyerName: "Řád\tx", BuyerStreet: "S", BuyerCity: "C", BuyerZip: "11000"},
		Kind:  "invoice", Number: "UBY-2026-0042", VS: "20260042",
		IssueDate: "2026-11-01", DueDate: "2026-11-15", TotalHaler: -15000,
		Note: "Období: 01.11.2026 – 30.11.2026", CorrectionReason: "x\ny\u0001",
	}
	got := snapshotJSON(inv, []item{{"Předplatné", 149}, {"Sleva", -15}})
	if got != pythonSnapshot {
		t.Fatalf("snapshot differs from Python:\n got %s\nwant %s", got, pythonSnapshot)
	}
}

func TestHelpers(t *testing.T) {
	for _, c := range []struct{ a, want int64 }{{14999, 149}, {-1499, -15}, {-1500, -15}, {0, 0}, {-1, -1}} {
		if got := floorDiv(c.a, 100); got != c.want {
			t.Errorf("floorDiv(%d, 100) = %d, want %d", c.a, got, c.want)
		}
	}
	for n, want := range map[int64]string{1: "1 apartmán", 2: "2 apartmány", 4: "4 apartmány", 5: "5 apartmánů", 0: "0 apartmánů", 21: "21 apartmánů"} {
		if got := apartmentsCS(n); got != want {
			t.Errorf("apartmentsCS(%d) = %q, want %q", n, got, want)
		}
	}
	if got := fmtDateRange("2026-11-01", "2026-11-30"); got != "01.11.2026 – 30.11.2026" {
		t.Errorf("range = %q", got)
	}
	if got := fmtDateRange("", "2026-11-30"); got != "30.11.2026" {
		t.Errorf("open range = %q", got)
	}
	if got := fmtDate("garbage"); got != "garbage" {
		t.Errorf("fmtDate passes through, got %q", got)
	}
}
