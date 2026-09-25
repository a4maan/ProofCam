# Step 3: Threat model, privacy rules, and assurance policy

Date: September 25, 2026  
Policy identifier: `proofcam-android-pilot-v1`  
Status: Engineering policy baseline; not implemented or independently audited. This is the internal data-handling policy, not a claim of legal compliance or a published service privacy notice.

Applies to the [Android photo pilot](02-pilot-scope-and-free-development.md). Armaan Singh is accountable for policy changes, private server access, incident response, and release decisions. Implementation, testing, and independent review remain later gates. All work uses free resources.

## Security objectives and limits

1. Never present a positive trusted-integrity result without a valid, trusted certificate and the corresponding exact file or canonical-pixel match.
2. Bind issuance to validated installation credentials, immutable export hashes, explicit evidence scope, and replay-safe server state.
3. Keep media and unnecessary identifying evidence off the server and out of public records.
4. Preserve captures through interruption and distinguish pending, rejected, and registered states.
5. Report uncertainty and unsupported evidence explicitly. Neither a watermark nor an installation signature proves that a sensor observed an unmodified real-world scene.

Assume the attacker knows the watermark algorithm and protocol, controls supplied files, copies valid records and watermarks, owns enrolled devices, instruments apps, alters local clocks, proxies assertions, and can photograph screens. Consider compromised operating systems, hostile networks, malicious administrators, credential theft, and service outages. Hardware-backed key protection does not prevent a compromised caller from requesting signatures in every circumstance.

ProofCam does not establish scene truth, absence of AI before final encoding, independently verified time/location, or a protected sensor-to-signature path. Unknown provenance does not imply fabrication. A service operator can correlate issuance and lookup traffic; this system is not anonymous.

## Assets and trust boundaries

| Boundary / asset | Trusted role | Untrusted input and required separation |
| --- | --- | --- |
| Camera and app process | Produce the intended final export | Camera input may be a display or staged scene; compromised clients can substitute content |
| App → installation key | Sign a typed, versioned request | Key possession is not scene provenance; private key remains nonexportable where supported |
| Imported file → parser/decoder | Parse only supported bounded formats | Treat pixels, container fields, dimensions, profiles, filenames, and embedded strings as attacker-controlled |
| App → registration service | TLS transport plus application signatures | Recompute request digest, validate evidence server-side; client booleans are not evidence |
| Service → certificate signer | Sign only a validated committed issuance transaction | Keep issuer key outside clients and source control; production and development trust roots are distinct |
| Lookup → verifier | Retrieve an untrusted candidate certificate | Verify signature, algorithm/version, issuer status, and content locally before displaying results |
| Operator → private database/backups | Maintain availability and deletion | Least-privilege access, private audit trail, encrypted backups, no private fields in public serializers |
| App → share destination | Release only the user's selected export/receipt | Destination can transform, retain, or republish it; receipt exports contain no management secrets |

Use configured HTTPS service endpoints only. An embedded identifier must never select an arbitrary URL. Keep production TLS verification enabled; development endpoints and development trust must be isolated in development builds.

## Threat register and required tests

| ID | Attack / failure | Required control | Acceptance evidence | Residual limit |
| --- | --- | --- | --- | --- |
| T01 | Copy watermark or attach another asset's record | Recovery is only discovery; exact comparison gates integrity | Unrelated and slightly edited media with copied IDs never receive positive integrity | Discovery can still return an unrelated valid record |
| T02 | Forge certificate or exploit algorithm confusion | Standard signature envelope, algorithm allowlist, typed/versioned serialization, domain separation | Forged, unknown-version, wrong-key, and malformed records fail closed | Compromised trusted issuer can misissue |
| T03 | Replay challenge or race two registrations | Random 256-bit session/installation-bound challenge; five-minute server expiry; atomic consume/create | Concurrent conflicting requests produce at most one committed record; identical retry returns same receipt | A valid fresh challenge is not proof of capture time |
| T04 | Relay assertion or substitute request | Bind available assertion to exact signed request digest; validate identity and freshness | Wrong installation, package, digest, session, and signing identity are rejected | Instrumented legitimate clients may still abuse signing |
| T05 | Inject gallery/generated media into capture path | No import-to-capture certification endpoint; narrow native capture path; explicit assurance scope | Modified binaries, camera substitution, signing-oracle and arbitrary-media injection tests | Without a protected sensor path, no universal injection-prevention claim |
| T06 | Present contradictory/rooted/emulated evidence | Server policy distinguishes missing evidence from failed validation | Decision matrix below exercised with recorded evidence fixtures | Undetected compromise remains possible |
| T07 | Modify stored export or canonicalization semantics | Reopen/hash final bytes; pinned decoder and golden vectors; immutable exports | Metadata-only edits, ICC/orientation cases, file corruption, and cross-build vectors | Unsupported semantics are uncheckable, not normalized into success |
| T08 | Malformed/oversized JPEG or PNG; expensive decoder search | Input caps, checked arithmetic, bounded work, sandboxing where possible, cancellation | Fuzz corpus, oversized dimensions, decompression bombs, time/memory limits | Parser vulnerabilities require continued updates |
| T09 | Steal management credentials or misuse removal API | Separate management authorization, fresh signed requests, recovery-secret verification, rate limits | ID/hash/receipt alone cannot delete; replay and cross-owner deletion fail | A stolen valid recovery secret grants its documented management scope |
| T10 | Leak enrollment, images, or lookup history | Local processing; field allowlists; redacted logs; no media telemetry; no bulk public listing | Traffic capture, exported-record inspection, backup/log tests | IDs and exact hashes are linkable; operator sees live requests |
| T11 | Crash, lose storage, expire challenge, or lose network | Durable queue, idempotency, preflight, explicit lower-assurance path | Restart each lifecycle transition; verify no false registered state or unexplained loss | Lost/uninstalled device without user export may lose local-only media |
| T12 | Steal issuer key, malicious admin, poisoned restore | Protected production signer, trust rotation/revocation, minimal privileges, deletion tombstones | Compromise drill; stale/revoked trust tests; restore suppresses deleted records | Revocation needs current information; copied records cannot be recalled |
| T13 | Tamper with APK or watermark-model update | Signed APK distribution; publisher fingerprint; signed/versioned model manifest if models are used; reject rollback outside policy | Modified packages/models and unauthorized versions rejected | Trust in the publisher is still required; sideload alone is not an attestation |
| T14 | Enumerate IDs, exhaust issuance/lookup resources | Random identifiers, no public enumeration, authenticated issuance, bounded quotas | Quota exhaustion returns clear retryable errors; no unbounded allocation or private details | Distributed denial of service may reduce availability |

## Capture-assurance decision policy

Certificates describe facts checked, never a single “authentic” grade. Store each check as `passed`, `failed`, `unavailable`, or `not_applicable`, with reason code, evidence scope, and policy version. Public records carry coarse results; raw evidence is private. Never collapse missing and failed evidence.

For this pilot, **basic integrity registration is available only to a server-admitted installation**: possession of the enrolled signing key must be verified; a private, single-use pilot invitation authorizes enrollment but establishes neither identity nor device integrity. Raw invitation codes are not retained. Do not expose an unauthenticated arbitrary-hash signing endpoint. This admission policy limits access; it cannot eliminate signing-oracle abuse by admitted attackers.

| Case | Registration decision | Permitted capture statements |
| --- | --- | --- |
| Valid enrollment/signature, fresh bound challenge, and all required available platform evidence validates | Issue if production signing is available | List exactly the app/device/challenge checks passed, each with time scope; no sensor-origin claim |
| Direct APK install; platform checks unavailable or unsupported, valid admitted enrollment/signature | Basic integrity certificate only | “Registered export; app/device capture assurance unavailable”; independently validated enrollment-key evidence may be listed at enrollment scope |
| Sideload yields licensing/recognition verdicts without Play entitlement/recognition | Treat those particular fields as unavailable assurance for this distribution policy, not proof of malware | Never claim Play-recognized/licensed status; separately check all supplied cryptographic evidence and any known signing identity |
| Valid enrollment/signature, offline capture | Queue; issue basic integrity certificate after successful synchronization | No fresh capture challenge; later evidence applies to synchronization only |
| Original online challenge expired before accepted registration | Reject online claim; allow explicit newly signed reduced-assurance request referencing original session and unchanged asset hashes, if no other validation failed | No fresh capture challenge; never replace it with a new capture challenge for old bytes |
| Attestation service/network temporarily unavailable | Keep online request pending until expiry, or explicitly choose reduced assurance and sign a new request | No unavailable check can be reported passed; do not strip a previously observed failure |
| Invalid signature, digest/package/signing-identity mismatch, revoked key/chain, contradictory evidence, failed required device validation, forged token, replay, or conflicting ID | Reject certification; retain local media with reason | No trusted capture claim; do not retry under reduced assurance to hide the failure |
| Keystore/local signing unavailable or enrollment not yet admitted | Save locally; registration pending or unavailable | No public certificate until minimum signing/admission requirements are satisfied; first offline use may enroll later without retrospective evidence |
| Only development signer exists | Development record only; public verifier rejects development issuer | “Development record”; no production integrity badge |

A licensing absence alone is distinct from a failed cryptographic validation. If evidence reports a concrete mismatch against ProofCam's configured identity, the rejection rule takes precedence. A client reporting “unsupported” is not proof that a failed check was absent; the reduced path simply offers no platform capture-assurance claim. Known server-side failures remain associated with the session/installation under the private retention policy.

A valid signature from an admitted but unattested installation establishes signed submission and hash binding only. This is intentionally weaker than an attested app-capture claim. The UI must make that visible even when the supplied file exactly matches a trusted baseline.

Enrollment key attestation must be validated on the server against maintained trusted roots, revocation information, challenge binding, application identity where present, and relevant security levels. Key attestation at enrollment does not independently attest each later capture. Do not hard-code one eternal root or promote a client-reported hardware level. Android documents the server-side validation requirements in its [key attestation guidance](https://developer.android.com/privacy-and-security/security-key-attestation).

Play Integrity describes separate request-binding, licensing, app-recognition, and device verdicts. Sideloading can lack Play entitlement; these signals are not interchangeable. Validate any token used and its request digest/freshness server-side. See [Android's verdict definitions](https://developer.android.com/google/play/integrity/verdicts). Actual availability for our free distribution path must be demonstrated before enabling a claim.

## Verifier trust policy

- A green integrity result requires signature validity, trusted current issuer status, a supported schema/algorithm, and the matching exact file or defined-pixel hash.
- Record recovery alone, perceptual similarity, and client claims never qualify. Imported screenshots may recover IDs and still mismatch.
- Public verifier rejects development certificates. Unknown issuers do not become trusted because the media matches their hashes.
- Trust/revocation cache maximum age: 24 hours from authenticated refresh, tracked conservatively across restart. If freshness cannot be established, show signer status unknown/stale, even when signature mathematics and content comparisons pass.
- Known revocation overrides cache freshness. A compromise notice identifies affected keys/claims; no independent timestamp is inferred from server registration time. Without trustworthy independent timing, do not grandfather records merely because their claimed registration predates compromise.
- Registration time is the service's stated time. Claimed device time is user/device-reported. No exact location is collected in this pilot.
- Pending registration, missing record, unreachable service, invalid record, mismatch, and unsupported parsing remain separate outcomes. A removed record cannot be distinguished from a never-existing one via unauthenticated lookup.

## Data map and retention rules

Durations below are pilot implementation requirements, not measured deletion behavior. Backend retention clocks use server time. Public export fields use a strict allowlist; do not serialize internal database objects wholesale.

| Data | Location / access | Purpose | Retention / deletion |
| --- | --- | --- | --- |
| Final photos and local thumbnails | App-private device storage; shared only by user action | User's capture library | Until explicit local deletion or uninstall; no automatic cloud backup |
| Working capture buffers/files | Protected device storage only | Finalization and crash recovery | Delete after verified final export is durably stored; clean abandoned work within 24 hours of next app run only when a safe export exists or user explicitly discards it; preserve sole recoverable capture |
| Imported verification copy and decoded buffers | Device only | Local extraction/hash | Release on completion/cancel; remove crash leftovers on next launch, without deleting the source file |
| Local installation private key, queue, management credentials | Keystore/app-private storage; exclude from backup/transfer | Signing, retries, ownership | Until local reset/uninstall or explicit management reset; no raw private-key export; new installation requires new enrollment |
| Public certificate | Public lookup and optionally user-exported receipt | Verify registered baseline | Until authorized public removal; indefinite while published, subject to service availability; others may keep copies indefinitely |
| Public certificate fields | Public | Record lookup and integrity | Only ID, media type, hashes, dimensions, schema/model/algorithm/policy versions, issuer/key ID, certificate signature, declared device time/source, registration time, completion and coarse check results |
| Enrollment public key, private owner/asset mapping, check summaries | Restricted server tables | Validate issuance and authorize removal | While enrollment or records remain active; purge within 30 days after closure/removal of all associated records unless minimal revocation/tombstone entries are needed |
| Raw attestation tokens/chains and signed request evidence | Restricted server evidence store; never logs | Validation and short investigation window | Maximum 7 days; retain minimal validation summary/digest after raw evidence expires under enrollment retention |
| Raw invitation and recovery secrets | Raw invitation transient; recovery secret on device/user export only | Pilot admission and management recovery | Server stores scoped verifier/hash, not plaintext; remove verifier when revoked or associated management scope closes |
| Live challenges and pending server requests | Restricted server state | Freshness and replay prevention | Challenge expires in 5 minutes; purge uncommitted transient state after 24 hours; committed idempotency links follow active record lifetime, reduced to non-reuse tombstones on removal |
| Access/security logs | Restricted server; no bodies, auth headers, full URLs, record IDs/digests, or stable client fingerprints | Operations and abuse response | Maximum 7 days; prefer coarse event codes and aggregate counters; disable proxy defaults that record lookup IDs |
| Rate-limit state | Restricted, short-lived server memory/store | Abuse control | Prefer short-lived keyed IP representations; maximum 24 hours; raw IP handled transiently by network stack, not retained in application logs |
| Administrator audit events | Restricted append-only audit | Accountable changes and deletion/restore tracing | 90 days; action/time/operator/internal event ID only, no media or tokens |
| Private deletion/non-reuse tombstones | Restricted server and restore filter | Never republish or reuse removed IDs | Retain minimal random ID and removed marker for service lifetime; no retained media hash, certificate, or owner linkage in tombstone |
| Encrypted server backups | Operator-controlled private storage | Recovery | Rolling maximum 30 days; deleted data may persist there until expiry, but must never be restored to public access |
| Diagnostics | Local redacted report; optional manual user export | Debugging | No automatic upload; if user submits to operator, delete within 7 days; never request raw photos, faces, credentials, or location as default diagnostics |

Exact content hashes and random record IDs are public and linkable. Do not describe them as anonymized. Service can link private issuance records to an installation and observe network requests while handling them. Operator access must be limited to the named accountable owner until another operator is explicitly designated.

Do not use public GitHub repositories/releases for participant records, private enrollment evidence, logs, backups, or recovery credentials. Signed application binaries and non-sensitive documentation may be distributed there. A free service whose logging/deletion controls cannot meet this policy is unsuitable for participant data; use local development with synthetic records instead.

## Permissions, disclosure, and network rules

- Ask for camera permission only when entering capture. Verification uses a system picker/share intent with narrow URI access; do not request broad photo-library access to verify one file.
- No microphone, contacts, location, advertising identifier, or analytics SDK in the photo pilot. Strip unnecessary export metadata; use generated filenames without identity or location.
- Tell users before first registration that record IDs/hashes are public, the service sees requests, registration requires network access, and public removal cannot recall copies.
- Extraction and hashing run locally. ID lookup is the disclosed verification action; exact-file-digest lookup requires explicit user approval. Never upload images or perceptual descriptors by default.
- Explicit sharing/export is a user's action to an external destination with its own retention behavior. A public receipt is distinct from a secret management-recovery export; never bundle them.
- Disable automatic backup of media, queues, credentials, and private app evidence with explicit cloud-backup and device-transfer exclusions. Test both paths on supported devices; do not rely only on a single manifest flag. Android documents separate backup and transfer rules in [Auto Backup guidance](https://developer.android.com/identity/data/autobackup).
- Opt-in diagnostics are separate from using capture/verification. No sensitive values in crash reports, network traces, filenames, or exception messages.

## Removal, recovery, and restore behavior

1. Public record ID, exact hash, or copied receipt does not authorize management. Removal requires an enrolled-owner request signed with a fresh management challenge or proof of a valid scoped recovery credential. Protocol bytes and recovery format are frozen at goal 9.
2. Generate a cryptographically random recovery secret with at least 256 bits of entropy, scoped to the installation's management records. Explain that possession grants removal/recovery authority, not capture signing. Store only a server-side verifier; rate-limit attempts. Rotation invalidates the prior secret.
3. User can remove a public record without deleting the local photo, or delete the local photo without removing the public record. Explain both choices. Canceling a pending registration must reconcile any in-flight server commit before claiming public removal.
4. An accepted public removal deletes the live certificate, lookup/digest indexes, and public caches within 24 hours; show removal pending until confirmed. Install a private tombstone in the same durable transaction so the identifier can never be reissued. Private related data follows the retention table.
5. Before restored storage serves any lookup, replay an authoritative deletion journal through the latest acknowledged deletion. If that journal is unavailable or incomplete, keep lookup offline until reconciliation; do not expose the restored snapshot. Test this even on free hosting.
6. After uninstall/key loss, create a new installation key. An exported recovery credential may authorize management of old records, but cannot restore the old capture key or retroactively validate captures. Losing all management credentials means losing self-service removal access; a public receipt is not a replacement.
7. Previously exported receipts remain mathematically signature-checkable under the current issuer trust policy. Record removal is distinct from issuer revocation. Without a current lookup, an offline verifier cannot establish current record availability.

## Initial resource limits

These conservative pilot limits are engineering choices to benchmark, not platform capability claims. Raise them only with measured memory/time evidence and a policy/version change.

- Verification inputs: JPEG or PNG, maximum 25 MiB encoded, maximum 20 million pixels, neither dimension above 16,384; reject before full allocation where possible. Reject animated/multi-image or unsupported rendering semantics.
- Recovery: at most 32 total candidate-region/scale/model combinations per input, at most 2 decoder versions within that shared budget, and a 15-second worker deadline; user cancel must stop work. Report unsupported decoder or recovery unsuccessful accurately. Historical decoder support cannot be silently dropped to satisfy this bound; route using known versions or offer an explicit version-specific attempt.
- Peak incremental memory target remains below 512 MB. Stream file hashing and use bounded image buffers; no unlimited retries.
- Per admitted installation: initially 100 registrations/day, 10 challenge requests/minute, and 1 active challenge per session. Verifier lookup: 60 requests/minute per short-lived network quota key with small bounded bursts; shared networks may need a documented adjustment.
- Queue retries use exponential backoff with jitter, respect server retry hints, and remain bounded per time window. Limits must not delete pending media or generate unlimited background jobs.

## Incident response and release gates

If issuer compromise is suspected: stop issuance, preserve minimal permitted audit evidence, revoke/rotate the affected key through the trusted update channel, and keep unknown scope conservative. Restore only after key separation and validation. Private evidence exposure requires stopping the affected path, determining scope, deleting exposed copies where controllable, and informing affected pilot participants through the established pilot contact process; do not promise copies can be recalled.

A public deployment still requires protected production signing under CAP7, tested revocations, privacy traffic audit, deletion/restore tests, and independent security review. No-cost development does not waive these gates. If compliant free infrastructure is unavailable, continue locally and label deployment pending.

Release is blocked by false positive integrity, prohibited data leakage, canonicalization disagreement, replay acceptance, unsigned model updates if models are used, or unexplained media loss. Goal 18 must exercise T01–T14 and every assurance branch above, including absence versus failure and sideloaded distribution. Evidence must be recorded; this document is not a passed test report.

## Step 3 completion and handoff

The threat register, trust boundaries, assurance decisions, data map, retention/removal rules, resource limits, and review gates are now defined. Goal 4 can design screens for these exact states. Goal 9 must encode the policy into schemas, golden vectors, endpoint contracts, replay rules, and recovery protocol. Platform documentation was checked September 25, 2026; recheck attestation roots and distribution requirements at implementation and before release.
