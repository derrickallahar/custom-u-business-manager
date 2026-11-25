# Custom U staff training

The live entry point is **HR & time clock → Training → Open Training** (`/hr/training`).

The current course, **Operating Custom U Business Manager** (edition 2), contains ten lessons and a twenty-question test. Its pass mark is 80 percent (sixteen correct). The printable guide is generated from the same saved course as the online lessons. The official Custom U logo appears on every page. The manager answer key is a separate protected download.

## For employees

Open a published course, read each lesson and use **Mark read and continue**. Return at any time to resume. Once every lesson is marked read, complete all test questions and confirm your own participation. The server grades the test and records the score, attempt and first successful completion time against that course edition. Failed attempts can be retaken. Earlier passes are never erased by later attempts. Downloading the PDF alone does not complete training.

## For HR managers and administrators

Use **Create training** to add lessons and multiple-choice questions (two to six choices, one correct answer). Set the introduction, edition, estimated duration and pass mark. Save and review the draft before publishing. Drafts and answer keys are visible only to HR managers and administrators.

Open a published course and expand **Assign course and set a due date**. Assign all staff, including future accounts, or select individual staff. An empty selection makes the course optional. The first course is published but not automatically assigned. No emails are sent by training actions.

Use **View team progress and results** for staff progress, scores, attempt counts and completion dates. Download the CSV for a staff review. The report shows the most recent 1,000 attempts; all attempts remain in the database and HR backup.

Published content is immutable. Use **Create a new edition** for revised lessons or questions and assign the new edition when retraining is needed. Archiving closes new attempts and preserves existing results. Assignment changes do not erase progress.

The encrypted **HR backup** includes courses, assignments, progress, attempts, management history and retry receipts. Existing older HR backups remain readable by the validator. Keep the HR backup alongside the separate workspace backup.

## Limits and deployment

This version supports text lessons and multiple-choice tests. It records knowledge-test completion and does not certify practical competence, attendance or identity beyond the signed-in staff account. Practical demonstrations remain a supervisor activity. It does not add video hosting, attachment uploads, recurring assignment automation or outbound reminders.

Apply `supabase/migrations/*_hr_training_127.sql` before deploying the application files. The migration adds private tables and a gated RPC, seeds the initial course once and leaves existing HR and commercial records intact. The application uses the existing sign-in, approved-computer and office-network checks. No new runtime setting or API subscription is needed.

## Planned time-off notice (edition 2)

The Time off screen and current guide use the approved policy wording: planned personal leave needs at least 24 hours before its start, and vacation needs at least 14 calendar days before its first day. Sick and emergency requests remain available for manager review. Statutory entitlements can be raised with HR using the appropriate leave type and note. Submission is never approval.

Personal requests capture a start time in Nassau time (09:00 by default for a full standard day). The server checks elapsed seconds for personal leave and Nassau calendar dates for vacation, always against the original server-recorded submission timestamp. Late requests can be recorded and declined or cancelled, but neither managers nor administrators can approve them. Existing approved leave is retained. Clock calculations and time-in-lieu balances are unchanged.

Migration 128 publishes edition 2, carries existing assignments forward and archives edition 1 without changing its content or past results. New-edition progress starts separately. The current printable guide is generated from `production_history/training_starter_128.json`.
