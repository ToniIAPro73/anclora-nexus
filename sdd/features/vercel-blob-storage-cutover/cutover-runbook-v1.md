# Nexus Storage Cutover Runbook v1

The code changes are staged behind `NEXUS_STORAGE_PROVIDER=supabase`. Do not change it to `vercel_blob` until every in-scope source object is copied and verified and Preview is reviewed.

## Provisioning and copy

1. The **private** Vercel Blob store `nexus-private-files` is created and connected to the Nexus Vercel project for Preview and Production. Add its read-write token to the Render API service as `BLOB_READ_WRITE_TOKEN` before using Blob. Keep the token server-side.
2. Keep Render's `NEXUS_STORAGE_PROVIDER=supabase` while deploying the facade and running the copy.
3. In a secured local shell, set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `BLOB_READ_WRITE_TOKEN`. Do not paste their values into chat, source files, or command history.
4. The migration credentials are stored locally at `~/.config/anclora/nexus-storage-migration.env` with mode `0600`; do not print or commit them.
5. Run an inventory first with `--dry-run --buckets dms,avatars`, then copy only those buckets. The script copies files under `bucket/path`, verifies each Blob object against its source bytes using SHA-256, and never deletes source files.
6. Verified copy on 2026-10-27: 15 `dms` objects (1,653,132 bytes) and 2 `avatars` objects (633,270 bytes), 17 objects total (2,286,402 bytes). The source Supabase objects remain intact.
7. Supabase `storage.objects` contains no objects outside `dms` and `avatars`. Neon has 198 non-null `document_template_versions.storage_path` references assigned to `dms-templates`, but none matches a source object in that bucket. These appear to be unresolved legacy references; do not synthesize or copy files for them. Investigate/regenerate the templates before enabling Blob-backed template downloads.

## Production-only Render topology

Toni confirmed on 2026-10-27 that Nexus must continue to have only its existing Render `production` service; do not create a development service. That service currently runs branch `production`. Keep `NEXUS_STORAGE_PROVIDER=supabase` and do not change its environment until Toni reviews the code and explicitly authorizes production cutover.

The absence of a separate Preview API means the Render-backed API flow cannot be validated in a Render Preview. Before production cutover, validate locally against the production-backed dependencies with the dedicated QA identity, and validate the Vercel frontend Preview where available. Use a production rollout only after Toni reviews and explicitly authorizes it.

When cutover is authorized:

1. Configure `BLOB_READ_WRITE_TOKEN` on the existing Render Production API service. Keep the token server-side.
2. Deploy the reviewed backend code to the existing service while `NEXUS_STORAGE_PROVIDER=supabase` remains set.
3. After verifying copied avatar files, update each existing profile's `avatar_url` to `https://<Render API host>/api/profile/avatars/<user-id>/<filename>`, using the source object path to map the existing filename.
4. Set `NEXUS_STORAGE_PROVIDER=vercel_blob` on that service only after the token is configured and the copy report reconciles.
5. Validate DMS upload/download/version/signature flows and avatar display using the dedicated QA identity. Template version downloads must remain on Supabase or be regenerated until the 198 unresolved references have a verified source.

Do not delete Supabase buckets or objects during this migration. Retain them as rollback copies until an explicit cleanup decision.
