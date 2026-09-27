# Development provenance protocol v1

This protocol certifies **registration of an exact file hash**, not absence of AI. It is deliberately isolated from future production trust. The independent verifier never displays a production authenticity result.

## Encoding and signatures

Messages use deterministic CBOR with shortest definite-length encodings and length-first map-key ordering. Duplicate keys, trailing data, unknown fields, booleans, floats, indefinite containers and unexpected tags are rejected. Maximum envelope size: 16 KiB; nesting: 16; container entries: 64; structural nodes: 512. The only tag is COSE_Sign1 tag 18.

COSE structure: `18([protected, {}, payload_bytes, raw_signature])`. Protected headers must be exactly `{1: -7, 4: kid_bytes}`: ES256 with P-256/SHA-256 and a 64-byte `r || s` signature. `kid_bytes` is the ASCII lowercase SHA-256 hex digest of the 65-byte uncompressed X9.63 public key. No algorithm negotiation or unprotected key headers.

Signature input: deterministic CBOR of `["Signature1", protected_bytes, external_aad, payload_bytes]`. External AAD is UTF-8 `proofcam.dev.v1.` plus `enroll`, `challenge`, `register`, `remove`, or `certificate`. Payload `type` must equal that same domain string, and integer `version` must be 1. Signature randomness does not affect idempotency: the service hashes the canonical payload, not the envelope.

Implemented with [COSE structures from RFC 9052](https://www.rfc-editor.org/rfc/rfc9052.html) and [PyCA ECDSA primitives](https://cryptography.io/en/stable/hazmat/primitives/asymmetric/ec/). Swift uses [CryptoKit Secure Enclave P-256 signing](https://developer.apple.com/documentation/cryptokit/secureenclave/p256/signing/privatekey). CBOR serialization is protocol code; elliptic-curve operations use platform/library implementations.

## Request fields

All payloads include `type` and `version`; these additional fields are mandatory and exhaustive:

| Purpose | Fields |
| --- | --- |
| enroll | `public_key`: 65-byte uncompressed P-256 point; `invitation`: 32 random bytes |
| challenge | `session`: 32 lowercase hex chars; `purpose`: `register` or `remove` |
| register | `id`: 32 lowercase hex chars; `file_sha256`: 64 lowercase hex chars; `session`; `mode`: `online` or `offline`; `challenge`: 32 bytes online, null offline; `source`: `import` or `camera_unverified` |
| remove | `id`, `session`, `challenge`: 32 bytes |

Enrollment verifies the self-signature and consumes an unexpired invitation in the same transaction that admits the key. The invitation is admission, not identity verification. Only its digest is stored. Successful identical enrollment retries are accepted unless the installation is revoked. Invitations expire after 24 hours; registration challenges after five minutes. Current server time is authoritative.

Challenges are bound to the authenticated installation, session and operation. Repeating a live challenge request returns the same challenge. Expired/consumed sessions cannot refresh that challenge while retained. A passing challenge establishes freshness at **registration**, not freshness of capture. Offline requests never gain a fresh-challenge result.

## Certificates and trust

Signed public certificate fields: `type`, `version`, `environment: development`, `issuer`, `id`, `file_sha256`, `registered_at` (server Unix seconds), `policy: development-integrity-only-v1`, `checks`, `source_declaration`. No invitation, installation key/ID, session, challenge, original media, location or client timestamp is public. The file hash and record ID remain linkable.

`checks` contains exactly:

- `enrolled_key_signature: passed`
- `fresh_registration_challenge: passed` for online or `not_applicable` for offline
- `app_integrity: unavailable`
- `hardware_key: unavailable`
- `camera_origin: unavailable`
- `absence_of_ai: not_established`

`source_declaration` is untrusted client testimony even when signed. Dimensions, image format and canonical pixels are not certified: the server never receives or parses media. A certificate can describe any admitted file hash. Native capture is a narrower client path, not a new server assurance level.

The offline verifier accepts only an explicitly supplied, currently valid local trust store. It checks issuer key status, signature, domain, exact schema, record ID when supplied, assurance policy and file hash. Development trust requires explicit opt-in. It reports signature, issuer, content, capture checks and availability separately. No URLs or trust keys from the certificate are followed. Copied receipts can remain signature-valid after removal; offline availability is always `not_checked_offline`.

## Transactions, persistence and development transport

SQLite uses `BEGIN IMMEDIATE` and `synchronous=FULL`. Challenge consumption, quota change and record insertion commit together; no successful certificate response precedes commit. A stored exact retry returns the original certificate even after expiry. Ownership, ID conflict and tombstone checks precede new issuance. Revoked installations cannot make further requests, including retries. Signing/storage failure rolls back challenge consumption.

Removal verifies owner and fresh management challenge, deletes the live record and installs an ID-only tombstone in one transaction. The local prototype does not implement a separate authoritative deletion journal; do not restore old snapshots into a public service. Do not delete/reset its database while expecting replay/non-reuse guarantees to survive.

HTTP endpoints: POST `/v1/enroll`, `/v1/challenges`, `/v1/register`, `/v1/remove`; GET `/v1/records/{id}`. Bodies and successful responses are CBOR; certificate responses are COSE bytes. Errors expose short codes only. Development server binds only `127.0.0.1`, has a five-second socket timeout, bounded bodies and no CORS permission. It serves one request at a time and is not a production HTTP server. Basic quotas: ten new challenges/minute and 100 new registrations/day per installation, plus 120 transport requests/minute globally. Lookup, unauthenticated and idempotent requests count toward the transport quota.

The CLI does not follow redirects or proxies; it requires a loopback endpoint. No public or plaintext remote deployment is supported. Production HTTPS, trust lifecycle and attestation schemas require a separately reviewed protocol.
