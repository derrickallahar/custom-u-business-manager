# Safety and cost boundaries — v0.7.7

- The App Platform HTTPS URL is **publicly addressable**. The UI requires password-based authentication but that is not the same as a network-private app. Do not use real employees or clients.
- This is a low-cost **staging** test, using the pre-existing v0.7.6 fictional Supabase database schema. It does not change or copy your business's real SQLite database.
- Database connection string + CA certificate are runtime env values; code or GitHub MUST NOT include them.
- The application creates **no** customer emails, push notifications, reminders or real payment gateway transactions.
- Single web service instance only. No autoscaling in initial low-cost trial.
- DigitalOcean App Platform web service charges apply while deployed. Supabase Free may pause on inactivity; verify current allowances and backup policies.
- Supabase file storage is NOT integrated into this package. Artwork attachments require a later separately tested permission and storage implementation.
- The cloud staging release does NOT meet production authentication/security requirements: add MFA, trusted identity, backups, hosting restrictions, logging/monitoring and security assessment before using private business information.
- When you no longer need the staging host, **destroy the App Platform app** to stop future hosting charges (merely closing the tab does not stop billing).
