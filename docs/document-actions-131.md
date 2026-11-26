# Document actions · release 131

Saved Business Manager quotes and invoices now offer **Download PDF** in the document and saved list. Saved client catalogues offer **Download PDF** without opening another tab. Files contain the saved revision, official logo and existing bank details; unsaved edits are excluded.

**Convert to invoice** on a saved quote creates and opens a live draft invoice in the same tab. It works for saved drafts and finalised quotes, retains the exact quote revision, uses the customer's payment terms (due on receipt when no terms are set), and opens the existing invoice on a retry. It does not finalise the quote, issue the invoice or send email. Zero-VAT classification still requires review before invoice finalisation.

Administrators can use **Edit finalised → Save revision**. Staff access has separate **Edit finalised quotes** and **Edit finalised invoices** permissions for selected managers, independent of HR roles and ordinary draft/finalisation permissions. Cancel discards local edits. Saving keeps the number and issued status, increments the revision, and records full before/after snapshots with actor and timestamp. Stale conflicting edits fail safely. Customer/contact identity and seller details remain fixed; create a new document to change the party. Discount approvals remain administrator-controlled.

Invoice amounts and VAT classifications can be revised before financial entries exist. Once any payment, credit or refund has been recorded, line quantities/rates/amounts, VAT classifications and invoice date stay fixed. Text, billing details, due dates, notes and terms can still be revised; use credits/refunds for financial corrections. Existing receipts, credits, refunds, emails, linked jobs and source-quote previews retain their original revisions. Previously emailed documents are not replaced or resent automatically.

Imported ShopVox archive records remain historical and read-only. Their original PDF can be downloaded where it was included with the import; this release does not manufacture missing source invoices.

## Validation

- Isolated PGlite: migration applied twice; draft/finalised conversion and duplicate retries; manager/admin/ordinary staff permissions; network gate; stale versions; discount protection; linked and direct invoice revisions; retained quote/job snapshots; receipt, credit and refund versions; financial-history guards; zero-VAT review.
- JSDOM: finalised forms unlock for selected managers; save/cancel; item fields; customer identity lock; PDF attachment download with no new tab; conversion double-click guard.
- Flask/Python: authenticated PDF routes, unauthenticated/unauthorised denial, amendment permissions, conversion defaults, PDF content/logo/bank details, historical ledger validation.
- Offline recovery: full quote/invoice/payment/credit/refund audit replay, original source preservation, rejection of rewritten/missing history.
- PDF visual inspection: saved invoice layout, official logo, bank information and original quoted deposit.

No live customer documents, payments or staff permissions are changed by the migration.

## Deployment notes

The production database migration `document_actions_131` was applied before publishing the application. Quote, invoice, payment, credit, refund and staff-access record counts and content hashes were unchanged. Unauthenticated document requests remained denied. The user explicitly approved publication to the existing `derrickallahar/custom-u-business-manager` repository on 26 November 2026.
