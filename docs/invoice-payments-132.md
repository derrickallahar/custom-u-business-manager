# Invoice payments and pre-send review · release 132

When a payment is recorded in Business Manager, reopening the invoice shows the payment date, receipt number, amount and remaining balance. Several payments are listed individually. A fully paid invoice displays **Paid in full** and **Date paid**, using the latest date among its active payments. Dates are the recorded payment dates, not the date the entry was entered. The saved invoice amount and revision are unchanged.

Invoice HTML previews, fresh PDF downloads and newly prepared email attachments include the same settlement information. Reversed payments are excluded. Credits and refunds are shown separately: a credited or mixed payment/credit settlement is not labelled paid in full. Test invoices remain clearly marked as practice. Draft invoices do not claim a payment status. A missing or inconsistent live ledger blocks document generation instead of implying that nothing has been paid.

The invoice payment pane can be refreshed and refreshes on returning to the page. It is available to users who may view invoices; it exposes dates, receipt numbers and amounts only, without granting permission to record/reverse payments or exposing internal notes. Reads lock the invoice while collecting payment and adjustment data so concurrent ledger writes cannot produce a mixed summary. Existing network/device and staff access checks still apply.

In **Email / history → Review email and PDF**, use **Open PDF preview in a new tab** for invoices, quotes and client catalogues. A separate **Download PDF** link remains available. Both links use the same prepared attachment. Ordinary navigation stays in the same tab. Return to the email screen, confirm the review and explicitly select **Send this email**. No preview action sends email. Changing email details clears the review. A change to invoice payments between review and send requires a fresh preview. Previously emailed/retained PDFs and copies already downloaded remain unchanged.

This reads existing Business Manager payment records; it does not add bank integration or infer missing payment dates in historical ShopVox PDFs. Those source files remain unchanged.

## Validation

- Isolated PGlite: migration replay, unpaid/partial/full payment, dates, reversal, credit/refund, private-field exclusion, view-only staff, blocked/unauthenticated access, no private function grants and unchanged invoice snapshots/audit on read.
- Python/Flask: consistent amounts and dates; invalid summaries rejected; HTML/PDF parity; deterministic PDF bytes, logo/bank details, long payment-history pagination, test/draft labelling; access checks; stale email review rejected; retained emailed bytes preserved. No real email is sent.
- JSDOM: all three pre-send previews open in a new tab even with shared navigation active; matching separate downloads; normal links retain the same tab; review confirmation and invalidation; payment refresh, return navigation, stale/error states and sign-out clearing.
- Release 131 regression checks: conversion/revision permissions, document downloads, financial-history guard and offline audit replay.
- Visual inspection of the generated invoice PDF and payment history.

## Deployment

Apply the read-only `invoice_payments_132` database migration before deploying the application. No existing invoice, payment, credit, refund or staff permission is rewritten. After deployment, refresh Business Manager and reopen an invoice; no configuration or data re-entry is required.
