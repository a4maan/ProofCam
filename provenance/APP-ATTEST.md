# App Attest validation layer

The local service now validates an iOS App Attest certificate chain and request assertions under an explicit app/environment/build policy. It binds the App Attest key to the already admitted installation key and binds each assertion to the exact signed registration request. Camera origin and absence of AI remain unverified.

**Activation constraint:** Apple's [iOS capability table](https://developer.apple.com/help/account/reference/supported-capabilities-ios) lists App Attest for Developer Program/Enterprise members, not free Personal Teams. No membership was purchased. Default builds keep this integration inactive, preserving free camera/signing tests. Activate only with an already eligible team and provisioning profile. Live Apple issuance, SDK compilation and iPhone operation have not been tested here.

## Validation scope

Implementation follows Apple's [server validation guidance](https://developer.apple.com/documentation/devicecheck/validating-apps-that-connect-to-your-server) and [client integration guidance](https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity). The [public root](https://www.apple.com/certificateauthority/private/) is bundled and SHA-256 pinned; client-supplied trust roots and URLs are never accepted.

Checks cover certificate signatures, validity, constraints and credential-key type; nonce and installation/challenge binding; key identifier and COSE-key agreement; application identity; environment; initial counter; signed build/category policy; assertion signatures; increasing counters; and fresh registration challenges. Unrecognized critical certificate extensions, unsupported authenticator flags, missing build extensions and malformed CBOR fail closed.

This is a **strict iOS profile**: attestation flags `0xc0`, assertion flags `0x80`, definite CBOR, a 77-byte P-256 COSE key and signed version/category extensions. Older authenticators without the required extensions are unsupported, not silently accepted. The default development policy accepts category 3 and build `1`; the app's current CFBundleVersion is 1. Verify the actual signed build signal on the phone before changing policy. macOS App Attest/ACL validation is not implemented.

Receipt/fraud-metric assessment and online certificate revocation checks are **not implemented**. Only a receipt digest is retained on the server, with `receipt_assessment: not_performed`. Therefore this is a scoped cryptographic validator, not the complete Apple fraud-assessment pipeline or production capture assurance. Broad `app_integrity`, capture-key hardware assurance and camera-origin results stay `unavailable`. The separate `app_attest` certificate field reports `cryptographic_checks_passed` only for chains anchored to the pinned Apple root. Synthetic test roots always produce `synthetic_test_only` and have no CLI configuration path.

## Server configuration

Copy the example to ignored local storage, then replace its app ID prefix with the actual **App ID prefix** from the provisioning configuration. It is often the team ID but must not be assumed to be identical.

```sh
cp provenance/app-attest.example.json provenance/local/app-attest.json
# Edit provenance/local/app-attest.json to match your actual signed app identity.
.venv-provenance/bin/python -m provenance serve --app-attest-config provenance/local/app-attest.json
```

The policy fingerprint is stored in the database; changing the identity/environment/build policy on an existing registry is rejected. There is no unreviewed policy migration/reset command. Use a separate disposable development registry/issuer when testing a different policy; do not reset a registry whose records/tombstones must survive. Existing basic records are preserved.

## iPhone configuration

For an eligible development provisioning profile, set these target build settings in Xcode:

- `PROOFCAM_APP_ATTEST_ENABLED = YES`
- `PROOFCAM_APP_ATTEST_ENTITLEMENTS = ProofCamResearch/AppAttest.entitlements`

Enable the App Attest capability for the registered App ID and use matching provisioning. The provided entitlement selects the **development** environment. Do not change only the server to production; environments and provisioning must agree. Apple's [environment guidance](https://developer.apple.com/documentation/devicecheck/preparing-to-use-the-app-attest-service) explains their separation.

Run `bash ios-benchmark/tools/validate-mac.sh`, then install on the physical iPhone. Default unsigned simulator validation does not activate App Attest. App Attest calls contact Apple; the app still does not upload photos or contact the ProofCam registry directly. No software-key/fake-token fallback exists.

## Enroll the App Attest key

First complete ordinary device enrollment from [the local setup guide](README.md). App Attest admission is an additional step, not a substitute for the invitation and installation signature.

1. In the app, choose **Export App Attest challenge request**. Transfer the signed CBOR file to the Mac.
2. Submit it and convert the response for phone import:

   ```sh
   .venv-provenance/bin/python -m provenance submit --kind challenges --request /path/to/attest-challenge-request.cbor --out provenance/local/attest-challenge.cbor
   .venv-provenance/bin/python -m provenance challenge-json --input provenance/local/attest-challenge.cbor --out provenance/local/attest-challenge.json
   ```

3. Within the five-minute server window, transfer that JSON to the phone and choose **Import App Attest challenge JSON**. The app generates/reuses its separate App Attest key, obtains Apple's evidence, and exports a device-signed enrollment request. Save it privately and transfer it back.
4. Submit the exact saved request:

   ```sh
   .venv-provenance/bin/python -m provenance submit --kind attest --request /path/to/app-attest-enrollment.cbor --out provenance/local/app-attest-result.cbor
   ```

Evidence exports are retained in protected local app storage and listed for re-export after relaunch. Re-importing the same session returns its existing saved artifact without another Apple call. Do not regenerate evidence just to retry an interrupted submission. Expired uncommitted challenges require a new session; exact committed retries are idempotent. Apple service failures remain failures/pending work, with no automatic downgrade.

## Register a capture with an assertion

For a **new, not-yet-registered capture**, choose its **Export registration challenge request** button. Submit/convert the challenge as above, using fresh output filenames. Import the JSON through that capture's **Import registration challenge JSON** button. The app hashes the stored final JPEG, signs an online registration request, and obtains an App Attest assertion bound to those exact request bytes.

```sh
.venv-provenance/bin/python -m provenance submit --kind register-attested --request /path/to/app-attest-registration.cbor --out provenance/local/attested-certificate.cbor
.venv-provenance/bin/python -m provenance verify --file /path/to/capture.jpg --certificate provenance/local/attested-certificate.cbor --trust provenance/local/trust.cbor --allow-development
```

The fresh challenge applies to registration, **not the earlier camera exposure**. App Attest does not prove the scene was not AI-generated. A previously registered basic record cannot be silently upgraded in place under the same ID.

After binding an installation, basic registration without an assertion is rejected, even if the server restarts without attestation configuration. Counter advancement, challenge consumption, issuance and exact-bundle retry tracking are atomic. Authenticated cryptographic failures persist an installation block under the same database writer lock; retrying through the basic endpoint cannot hide them. No automatic unblock exists. An operator must investigate; revocation remains available. Serialize submissions: out-of-order counters are rejected conservatively.

## Evidence and remaining tests

The test suite uses a synthetic root/intermediate/credential chain to exercise successful validation and failures. It checks wrong roots, identity/environment/build/category/nonce, altered certificates and keys, malformed evidence, counter replay, assertion substitution, cross-owner key reuse, omitted assertions, atomic failure blocking, rollback, restart, concurrent identical retries and HTTP/CLI handoff. Cross-language tests compare exact Swift/Python context and request bytes. See [validation metadata](validation.json).

These tests do not demonstrate acceptance of a genuine Apple attestation. On an eligible Mac/iPhone setup, check actual certificate/extension compatibility, provisioning denial, Apple outages, challenge expiry during transfer, relaunch/re-export, key loss, out-of-order assertions and exact-file verification. Complete receipt/risk handling, revocation strategy and an independent security review before any production claim.
