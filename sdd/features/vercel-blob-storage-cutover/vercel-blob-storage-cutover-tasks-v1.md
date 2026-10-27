# Vercel Blob Storage Cutover — Tasks v1

- [x] Confirm the official Python SDK package/API and pin a compatible release (`vercel-blob==0.5.0`).
- [x] Add a server-side storage facade; keep Supabase as the default provider until cutover.
- [x] Route DMS uploads/downloads through the provider facade without changing database references.
- [x] Add authenticated avatar upload through FastAPI; serve avatars via a constrained public image proxy.
- [x] Update the profile UI to upload avatars through the authenticated backend.
- [x] Add an idempotent storage copier that verifies object count, byte size, and SHA-256 without deleting source objects.
- [x] Create the private `nexus-private-files` store and connect it to the Nexus Vercel project for Preview and Production.
- [x] Keep the existing production-only Render topology; do not create a development service.
- [ ] Validate local and Vercel frontend Preview flows before requesting production cutover.
- [ ] After explicit production-cutover authorization, add the store token to the existing Render Production API service as `BLOB_READ_WRITE_TOKEN`.
- [x] Run a dry-run inventory and reconcile the copier scope against the source inventory.
- [x] Copy and verify 15 DMS objects and 2 avatars (2,286,402 bytes total); retain all Supabase source objects.
- [x] Identify 198 Neon template path references with no matching Supabase object; keep template cutover blocked pending remediation.
- [ ] Add the store token to the Render API Preview service as `BLOB_READ_WRITE_TOKEN`.
- [ ] Update existing avatar URLs after copied files are available through the API proxy.
- [ ] Validate Preview DMS and avatar flows with the dedicated QA identity.
- [ ] Keep Supabase source buckets intact until Toni validates Preview and authorizes production cutover.
