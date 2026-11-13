// Package billingjob is the Go port of UbyHost's own invoicing to hosts
// (App/app/billing_invoices.py, brief 1221): numbering, the stored snapshot, the
// PDF, storno, and the billing_invoice mail. The billing job itself (trial, roll,
// follow_apartments, dunning) is brief 1222 and builds on this package.
//
// Invoicer.IssueForPeriod, IssueSupplementary and Storno issue one document in a
// single transaction exactly as Python's issue() does, and write the audit row
// platform_invoice_issued after the commit. Invoicer.Send queues the mail.
//
// Known differences from Python: the PDF bytes (and so pdf_sha256) come from
// go/internal/pdf, not reportlab; whitespace around buyer_name is judged with
// strings.TrimSpace, not Python's str.strip.
package billingjob
