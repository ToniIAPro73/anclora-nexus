# Neon database migrations — Anclora Nexus

Neon is the sole application database provider. The application uses Neon Data API and Neon PostgreSQL; authentication is provided by Anclora Identity, and file objects use Vercel Blob. There is no active Supabase runtime or Supabase migration CLI configuration.

## Active migrations

- `000_prepare_neon_data_api_roles.sql`: prepares imported database roles for Neon-managed Data API roles.
- `001_neon_data_api_access_security.sql`: configures database access and row-level security for the Data API.
- `002_neon_identity_claims.sql`: aligns authorization policies with Anclora Identity JWT claims.

Apply migrations only through the governed Neon production-backed workflow and verify the target branch before execution. Do not create a separate development database.

## Historical archive

`archive/` retains the former Supabase migration SQL, seed and verification files, and temporary Neon CLI material for traceability. These files document the database's history; they are not current Supabase configuration and must not be replayed as a fresh migration sequence. The historical SQL may retain original Supabase naming and assumptions by design.

## Current implementation state

- Active frontend and backend code use Neon Data API for application database operations.
- Anclora Identity is the application authentication and session provider.
- Vercel Blob is the object-storage provider.
- The Supabase project is not used by the current runtime. Retained references are confined to historical evidence/archive or upstream compatibility dependency metadata.
- Production-backed QA and remote schema/migration state are governed by `.anclora/PRODUCTION_RUNTIME.md`; this README does not claim that a remote migration was applied unless the deployment record says so.
