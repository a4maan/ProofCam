# Local provenance infrastructure

ProofCam can now enroll a signing key, submit a device-signed file hash, issue a signed development certificate, and independently check that a file matches that certificate. The iPhone research app adds a camera-only capture route and Secure Enclave signing. **No certificate produced by this implementation establishes that an image was not AI-generated or that its pixels came from a protected sensor path.**

This is a free, local development system. It is not deployed and is not a production trust authority. No media is uploaded. The service accepts only bounded signed CBOR requests; public lookup returns only an allowlisted certificate. It runs on loopback, with no network-interface override. Use synthetic/test material only.

## What is implemented

- Single-use, expiring private enrollment invitations and proof of possession of a P-256 installation key.
- COSE_Sign1 ES256 signatures, deterministic CBOR, algorithm allowlists, explicit message versions and domain separation.
- Five-minute random 256-bit challenges bound to the installation, session and operation. The claim is **fresh registration challenge**, never camera time or sensor origin.
- Atomic SQLite transactions for challenge consumption and record creation. Exact request retries return the same certificate after restart, including after challenge expiry; conflicting requests fail.
- Explicit offline registration without fresh-challenge assurance. Persisted request files support manual, idempotent retry.
- Pinned local issuer trust with expiry and key status. Development issuers are rejected unless the caller explicitly enables development verification.
- Independent signature verification and streaming SHA-256 file comparison. A copied ID or altered photo cannot earn an exact-byte match against another file's certificate.
- Owner-signed removal with a fresh management challenge, private non-reuse tombstones, and installation revocation.
- Request size/structure bounds, basic per-installation quotas, local transport rate limits, and no access logging of paths or bodies.
- iPhone camera callback → watermark → final JPEG saved and reopened → hash → Secure Enclave signature → protected local pending files. Gallery imports stay in the existing watermark research flow and cannot enter that camera callback through the UI.

The base certificate reports `app_integrity`, `hardware_key`, and `camera_origin` as `unavailable`, and `absence_of_ai` as `not_established`. Even the iPhone's locally hardware-protected key is **not server-attested**. Client declarations never upgrade these results. An optional [App Attest layer](APP-ATTEST.md) now adds separately scoped cryptographic request evidence after server validation; broad app integrity and camera-origin claims remain unavailable.

## Run locally

Use Python 3.11+ from the repository root:

```sh
python3 -m venv .venv-provenance
.venv-provenance/bin/python -m pip install -r provenance/requirements.txt
.venv-provenance/bin/python -m unittest discover -s provenance/tests -v
.venv-provenance/bin/python -m provenance init-server --out provenance/local/trust.cbor
.venv-provenance/bin/python -m provenance invite --out provenance/local/invitation.cbor
.venv-provenance/bin/python -m provenance serve
```

The last command runs the development service on `127.0.0.1:8765`. Keep that terminal open. On Linux, the distribution's Python venv support must be installed. Keys, database and example outputs live under the ignored `provenance/local/` directory. Issuer keys are development PEM files, not protected production signing keys. Use a private filesystem directory; POSIX permission settings do not substitute for Windows/WSL host access controls.

Trust files expire after 24 hours. Refresh deliberately with `export-trust --out provenance/local/trust-next.cbor`; distribute that file through a trusted local channel. The verifier never obtains trust roots from a certificate or a lookup endpoint. Existing output files are not overwritten. Files are staged privately, flushed to disk and atomically published only after a complete write. This requires a local filesystem supporting hard links. Interrupted pre-publication saves can leave private `.pending` staging files, which are never used as valid requests or keys. Input files must be regular files; pipes and device nodes are rejected.

## iPhone → local registration → independent verification

1. On your Mac, run `bash ios-benchmark/tools/validate-mac.sh`, then install the research app on the physical iPhone. Secure Enclave capture signing intentionally has no simulator/software-key fallback.
2. Create an invitation using the command above. Transfer that private `invitation.cbor` file to the phone. In **Capture provenance — development**, choose **Prepare device enrollment**, select the invitation, and save `proofcam-enrollment.cbor` privately. Transfer it back to your Mac. It contains the invitation; do not publish it.
3. Submit the signed enrollment while the server runs:

   ```sh
   .venv-provenance/bin/python -m provenance submit --kind enroll --request /path/to/proofcam-enrollment.cbor --out provenance/local/enrollment-result.cbor
   ```

4. Choose **Take and sign a photo**. The app keeps the final JPEG and signed offline registration request in protected app storage across launches. Export both files from the pending capture. Copy them to `provenance/local/capture.jpg` and `provenance/local/capture-request.cbor` on your Mac. The original record ID remains inside the signed request and watermark; changing the filenames is harmless.
5. Register and verify:

   ```sh
   .venv-provenance/bin/python -m provenance submit --request provenance/local/capture-request.cbor --out provenance/local/certificate.cbor
   .venv-provenance/bin/python -m provenance verify --file provenance/local/capture.jpg --certificate provenance/local/certificate.cbor --trust provenance/local/trust.cbor --allow-development
   ```

A successful development check reports `signature: valid`, `content: exact_match`, and **`absence_of_ai: not_established`**. Omit `--allow-development` to confirm the default rejection. Changing the JPEG produces `different_bytes` and exit status 2. Invalid signatures, trust or messages exit 1. Use `--id` to bind verification to an independently recovered watermark ID.

No app-to-server networking is required for this first implementation. Registration is a manual Mac step, not automatic upload or a background queue. Saving through a cloud-backed Files provider is an explicit user action; prefer local transfer for invitation and enrollment files. The app does not store the invitation after building the export, but exported copies should be removed after enrollment. Captures and pending requests stay local; failed finalization preserves any photo already written and exposes it for export after refresh. Uninstalling the app can lose these files: export them first.

## Exercise desktop registration without an iPhone

In a second terminal, use a new invitation if the first was consumed by the phone:

```sh
.venv-provenance/bin/python -m provenance keygen --key provenance/local/desktop-key.pem
.venv-provenance/bin/python -m provenance invite --out provenance/local/desktop-invitation.cbor
.venv-provenance/bin/python -m provenance enroll --key provenance/local/desktop-key.pem --invitation provenance/local/desktop-invitation.cbor
.venv-provenance/bin/python -m provenance challenge --key provenance/local/desktop-key.pem --out provenance/local/challenge.cbor
.venv-provenance/bin/python -m provenance prepare --key provenance/local/desktop-key.pem --file /path/to/test.jpg --id 00112233445566778899aabbccddeeff --challenge provenance/local/challenge.cbor --out provenance/local/request.cbor
.venv-provenance/bin/python -m provenance submit --request provenance/local/request.cbor --out provenance/local/desktop-certificate.cbor
```

The example ID is for one local experiment; use a fresh 128-bit random ID for each new asset, or the ID already embedded in its watermark. `prepare` always declares an import. Omit `--challenge` for an explicitly offline request. Submit the **same saved request** again to retry an interrupted registration; do not issue a new challenge to claim an earlier capture was fresh.

`lookup --id … --out …` fetches a candidate certificate without trusting it. `challenge --purpose remove …` followed by `remove --id … --challenge … --key …` removes an owned record. `revoke --installation …` is a local operator command disabling future installation requests; it does not revoke the issuer or retroactively erase copied receipts. Offline verification cannot establish current record availability. Repeated removal returns unavailable; a public lookup does not distinguish removed from never registered IDs.

## Evidence and remaining gates

See [protocol](PROTOCOL.md), [validation report](validation.json) and automated tests. Backend tests cover real loopback HTTP and separate-process CLI use, altered files, forged/wrong-domain signatures, default development rejection, admission, quotas, stale/revoked trust, conflicting/replayed requests, concurrent races, rollback, restart, removal and non-reuse. Swift tests compare exact CBOR/signature-input bytes against Python. Two CryptoKit cross-checks are prepared for Mac execution.

The follow-up audit expands the backend suite to **37 tests**, including actual process termination before/after commit, eight-way enrollment races, two-owner ID collisions, deletion rollback, malformed HTTP framing, 3,296 single-bit mutations of a signed request, 2,000 seeded random messages, and independent OpenSSL command-line signing/verification. It found and fixed two reliability defects: failed export publication and blocking named-pipe inputs. Atomic export races, simulated disk failures, empty/oversized inputs and the actual workspace filesystem are now checked. These are targeted engineering checks, not an independent security audit or exhaustive fuzzing.

The [dependency advisory snapshot](dependency-audit.json) records an [OSV query](https://google.github.io/osv.dev/post-v1-querybatch/) for the four pinned Python packages. No advisories were returned for those versions at the recorded time. This does not cover the host OS, Apple SDK or native libraries bundled in wheels; a clean result does not prove the dependencies are vulnerability-free.

**Not implemented or qualified:** live qualification and complete receipt/risk/revocation handling for Apple App Attest, Android attestation, protected sensor-to-signature provenance, production protected signing/trust distribution, canonical-pixel matching, automatic mobile registration/reconciliation, accountless recovery credentials, authoritative deletion-journal replay after backup restore, public hosting/TLS/operational hardening, full policy retention jobs, independent security review, and Android integration. App Attest cryptographic evidence has a separate strict issuance path. Failed or unsupported evidence cannot be supplied as a successful boolean or downgraded after an observed cryptographic failure.

The local reference service uses Python/SQLite to make this experiment runnable with current free tools. This is an explicit development implementation, not a silent replacement of the planned Rust/PostgreSQL production architecture. The `proofcam.dev.v1` wire domain and development-only issuer separate it from future production trust.

Apple compilation, camera/Secure Enclave behavior, permission denial, device lock/relaunch, storage interruption, backup exclusion and export behavior **must be tested on the Mac/iPhone**. A protected app key still does not prevent an instrumented client from requesting signatures or someone photographing an AI-generated image on a screen.
