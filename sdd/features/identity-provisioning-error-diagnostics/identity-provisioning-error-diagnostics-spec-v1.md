# Identity Provisioning Error Diagnostics — Spec v1

## Problem

Nexus reduces non-success responses from Anclora Identity to an exception type. Operators cannot distinguish a rejected credential, invalid request, or upstream failure when provisioning an approved access request.

## Objective

Retain the Identity HTTP status and a bounded, sanitized response body in the existing provisioning error field, the signed access-request audit event, and backend logs.

## Security requirements

- Never retain request headers, bearer credentials, cookies, invitation tokens, passwords, or private keys.
- Redact email addresses from retained response text and logs.
- Redact sensitive response fields and secret-like values in response text.
- Cap the retained response body at 2,048 characters and remove control characters.
- Preserve the existing generic error for failures without an HTTP response.
- Do not change access decisions, provisioning behavior, or database schema.

## Acceptance criteria

- Identity non-success responses retain their HTTP status and sanitized response body.
- The provisioning error remains available on the access-request record.
- The signed provisioning audit event contains the same diagnostic fields.
- Backend logs include the HTTP status and sanitized body without logging email addresses or request credentials.
- Network and unexpected exceptions do not expose exception text or secrets.
