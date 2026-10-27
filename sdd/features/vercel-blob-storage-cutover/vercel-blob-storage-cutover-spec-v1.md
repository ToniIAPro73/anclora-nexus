# Vercel Blob Storage Cutover — Specification v1

Status: **Code and Vercel token present; effective production selection unverified (2026-10-27).** The Render service metadata available during this audit did not expose `NEXUS_STORAGE_PROVIDER` or the Blob token. Do not claim the production storage cutover complete until those runtime settings and an authenticated DMS/avatar smoke are confirmed.

## Problem

Nexus still has Supabase Storage paths for DMS documents and profile avatars. Neon is the target for application data, but production database-provider selection is not verified; see the Neon runtime cutover specification. The FastAPI backend runs on Render and has a provider switch for DMS object operations whose active production value has not been verified.

## Goal

Move Nexus DMS files and profile avatar bytes to a private Vercel Blob store, independently of the application database and Anclora Identity. Avatars remain publicly viewable through a narrow API proxy, matching their existing public behavior without exposing the Blob token. Use Vercel's Python Blob SDK directly from the existing FastAPI service; do not add a Node storage bridge.

## Observed baseline (2026-10-26)

- Supabase buckets: `dms` (15 objects, about 1.65 MB), `avatars` (2 objects, about 633 KB), and empty `logos`.
- All 15 `dms` objects match the unique path references in current Neon `generated_documents` and `document_versions` records.
- Two profile avatar URLs are referenced by Neon `user_profiles`.
- DMS data includes encrypted source bytes, generated documents, versions, previews, and signed-document flows. Existing encryption bytes and metadata must remain unchanged during object copy.
- Some code paths use additional bucket defaults for signed documents and temporary exports; the migration must inventory these paths and map them into the private store with stable path prefixes.

## Scope

- Add the official Vercel Blob Python SDK to the Render backend and introduce a storage service abstraction for private upload, read, delete, and public avatar proxying.
- Replace direct Supabase Storage calls in DMS routes with the storage service.
- Replace browser-direct Supabase avatar uploads with an authenticated server-side upload flow; update the profile URL and identity-provider user metadata after upload succeeds where supported.
- Preserve current DMS pathnames at the application layer; namespace Blob objects as `bucket/path` to prevent collisions between Supabase buckets, without changing Neon references.
- Copy existing DMS objects and public avatar objects with byte/hash verification before changing application reads/writes.
- Keep authentication independent from storage and retain the Supabase buckets as rollback sources until the active Render storage provider is verified and an explicit production cutover is validated.

## Out of scope

- Changing authentication or migrating identity-provider accounts.
- Deleting Supabase buckets, users, or source objects.
- Changing the Neon schema or application database provider.
- Changing the Vercel frontend or Render backend hosting providers.

## Acceptance criteria

- AC1: DMS writes and reads use private Vercel Blob; the Blob token remains server-side in Render.
- AC2: DMS membership and `org_id` checks run before every file read, write, and delete.
- AC3: Existing 15 DMS objects are copied byte-for-byte and every source path has exactly one verified destination path.
- AC4: Existing Neon DMS path references continue to resolve after cutover.
- AC5: Avatar upload requires an authenticated user, writes only under that user's stable prefix, and updates the profile and identity-provider metadata only after upload succeeds where supported. Avatar bytes stay in private Blob and are served through a constrained image-only proxy.
- AC6: Empty buckets remain empty; no Supabase data is deleted during migration.
- AC7: The intended Render environment has `NEXUS_STORAGE_PROVIDER=vercel_blob` and the Blob token; authenticated DMS upload/download/version/signature flows and avatar upload pass before declaring production cutover.
