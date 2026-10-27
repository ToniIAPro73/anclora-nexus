# Vercel Blob Storage Cutover — Plan v1

1. Confirm the Vercel Python Blob SDK API and pin a compatible package version for the Render FastAPI runtime.
2. Add a provider-neutral storage facade and migrate backend DMS calls while retaining Supabase Auth and Neon data access.
3. Replace direct browser Supabase avatar uploads with an authenticated backend upload endpoint.
4. Create private and public Blob stores scoped to the Nexus project; provide the private token to Render and the public/private tokens only to server runtimes that need them.
5. Copy existing DMS objects to identical private pathnames and avatars to stable public paths; verify object count, byte size, and SHA-256 before cutover.
6. Validate on Preview with the dedicated Nexus QA identity, including DMS reads/writes and avatar update.
7. Keep Supabase buckets and objects intact through Toni's Preview review and explicit production cutover authorization.

No Auth provider, database provider, or hosting provider changes are part of this feature.
