# Bundle 29 — Trusted Proxy Rate-Limit Identity

## Purpose

Stop direct clients from changing rate-limit identity with spoofed forwarded headers.

## Rules

- Forwarded headers are ignored when proxy depth is zero.
- Positive proxy depth requires explicit trusted proxy CIDRs.
- The direct peer and configured proxy hops must be trusted.
- Invalid, incomplete or untrusted chains use the direct peer.
- Invalid proxy configuration fails application creation.

## Verification

Tests cover default spoofing, trusted one-hop and multi-hop chains, untrusted peers, malformed chains, startup rejection and middleware bucket behavior on Python 3.11 and 3.12.

## Donor note

`nulleimy/Applaylist-old` is classified as read-only donor material. No code from it is imported in this bundle.

## Rollback

Revert the Bundle 29 squash commit. No data rollback is required.
