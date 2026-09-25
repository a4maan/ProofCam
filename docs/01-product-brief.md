# Step 1: Product definition and pilot audience

Date: September 25, 2026  
Status: Working product baseline established; implementation and external validation pending.

## Product decision

Build an Android photo pilot for journalists and field documenters who share original photographs with editors or reviewers. A recipient should be able to determine whether a supplied photo exactly matches a registered export, inspect the signed record, and understand which capture checks passed.

The product addresses a specific problem: recipients often receive photos separated from their capture context, with removable metadata or transformations introduced by sharing tools. ProofCam binds the final exported photo to a signed record and attempts to recover that record's identifier from supported transformed copies.

The signed baseline starts after watermarking and final encoding. It does not establish whether the scene was staged, whether a display was photographed, or whether content was manipulated before that baseline was signed.

## Pilot audience

| Role | Context | Need |
| --- | --- | --- |
| Primary: field journalist or documenter | Captures photos on Android, sometimes without reliable connectivity | Save and share a photo without losing track of registration or its original export |
| Secondary: editor or reviewer | Receives an original or a copy through a sharing channel | Check an exact match and understand the limits of the capture evidence |
| Pilot operator | Supports a small cohort and investigates failures | See registration and service health without collecting participants' media by default |

Recruit a small, invitation-only pilot representing both capture and review roles. Android reviewers use the app's verifier initially. Browser verification is deferred, and this constraint must be explicit during recruitment. At least ten reviewers participate in the comprehension check.

Insurance adjudication, legal evidence workflows, mass consumer distribution, and manufacturer-certified sensor provenance are outside this initial product definition. Those audiences require separate research and acceptance criteria.

## Core user journeys

### 1. Capture online and share an original

1. The user opens Photo mode and grants camera permission.
2. The app obtains the available enrollment evidence and a fresh capture challenge.
3. The user takes a photo. The app normalizes rendering, embeds the identifier, encodes the JPEG, and checks the stored final export.
4. The app signs the request locally and registers it with the service.
5. After durable server acknowledgement, the app shows “Registered” and stores the signed receipt.
6. The user shares the immutable original through the Android share sheet. Explain that a destination may transform it; do not imply that every destination's behavior can be detected.

Success: the reviewer receives the original and independently obtains a trusted, valid record and an exact-file match.

### 2. Capture offline or during an outage

1. The user takes a photo without a usable connection.
2. The app finalizes, checks, and locally signs the export, then queues registration durably.
3. The user may share that export with a clear “Registration pending” status. Sharing does not cancel or complete registration.
4. Once connected, the app retries and stores the server receipt if accepted.
5. The record states that no fresh online challenge covered capture. Later synchronization cannot manufacture that claim.

Success: the photo survives restart and synchronization, with accurate registration and assurance status throughout. If required local signing is unavailable, the app may save the photo but must not present it as a signed, registration-ready export.

### 3. Verify a received photo

1. The reviewer imports a photo for verification; import does not grant an app-capture claim.
2. The app extracts the identifier and computes integrity information locally.
3. It looks up the signed record using the identifier. If recovery fails, it can offer an explicitly approved exact-file-digest lookup.
4. It checks the certificate, trust status, and supplied content independently.
5. It presents separate results for signature, issuer, content, capture checks, and availability.

Success: the reviewer can tell whether the supplied file or defined pixels match, and distinguish that result from record discovery alone.

### 4. Verify a screenshot or transformed copy

1. The reviewer imports a screenshot, resized image, or recompressed copy.
2. The app attempts local identifier recovery within the measured support envelope, offering media-region selection where needed.
3. If an identifier is recovered, the app retrieves and validates the candidate record.
4. If exact comparisons fail, it shows “Record recovered; content does not exactly match.”

Success: recovering a record never produces a positive integrity result without a corresponding exact match. The interface does not claim the copy was derived from that original or explain why it differs.

## Claim vocabulary

| Term or result | Meaning | Limit |
| --- | --- | --- |
| Record recovered | An embedded identifier locates a candidate record | Does not bind this photo to the record |
| Exact file match | Every supplied file byte matches the signed file hash | Requires a valid record and trusted issuer for a positive integrity result |
| Exact defined-content match | The canonical decoded pixels match the signed pixel hash | Does not assert unchanged file metadata; canonicalization must be supported |
| Content mismatch | The supplied content does not exactly match the signed baseline | Does not establish malicious editing or identify a cause |
| Content uncheckable | The verifier cannot perform a supported comparison | Is neither a match nor a mismatch |
| Capture checks | Specific validated app, device, and challenge checks, with their evidence scope | Do not establish scene truth or a manufacturer-certified sensor path |
| Registration pending | No successful registration acknowledgement has been received | Public lookup may not yet succeed |
| No record found | Lookup returned no record for the candidate identifier or digest | Does not mean the media is fake |

Record signature is reported as valid, invalid, or unsupported. Issuer status is reported separately as trusted, unknown, revoked, or stale, with the applicable trust policy. Pending synchronization, missing records, network failure, and unsupported decoding remain distinct states.

Do not use a generic “real,” “AI-free,” “authentic scene,” or “verified original camera scene” badge. A green integrity result requires both a trusted valid record and the corresponding content match. An exact comparison with an unknown or revoked issuer must not receive that positive trusted-integrity presentation.

## Concrete result examples

| Input or event | Expected presentation |
| --- | --- |
| Unchanged registered JPEG; valid certificate; trusted current issuer | “Exact file match”; show only capture checks that passed |
| Metadata removed, but canonical pixels unchanged | “Exact defined-content match”; file bytes differ |
| Screenshot that retains the ID but changes pixels | “Record recovered; content does not exactly match” |
| Watermark copied onto unrelated media | Candidate record may be recovered; exact comparison fails; no integrity badge |
| Unmarked image with no matching record | Recovery unsuccessful / no record found as applicable; no conclusion about truth or AI generation |
| Offline capture later registered | Report actual integrity result; explicitly no fresh online capture challenge |
| Genuine app photographs an AI image displayed on a screen | Exact integrity may pass for the exported photo; scene truth remains unestablished |
| Valid mathematical signature with a revoked issuer | Signature valid; issuer revoked; no trusted-integrity badge |
| Lookup fails because the service is unreachable | Network unavailable; do not label the media valid or invalid |

## Pilot success metrics

These are acceptance targets, not measured results. Technical targets come from the engineering specification and are evaluated at later roadmap gates.

| Measure | Pilot target | Evidence |
| --- | --- | --- |
| Claim comprehension | At least 9 of 10 reviewers distinguish recovery from integrity | Scenario questions covering originals, screenshots, copied watermarks, and missing provenance; retain anonymized aggregate results |
| End-to-end correctness | Each declared reference device completes capture → registration → independent verification, including an offline/restart case | Recorded QA runs and signed test fixtures |
| False positive integrity | Zero false exact-integrity results in the release test corpus | Adversarial report; do not interpret zero observations as zero real-world risk |
| Original export recovery | 100% correct complete-ID recovery and defined-content matches in the frozen original-export corpus | Versioned held-out evaluation |
| Screenshot usefulness | At least 95% correct-ID recovery per declared device/size bucket after region selection | Actual screenshot tests; automatic region-selection results reported separately |
| Visual quality | Mean SSIM ≥0.98 and fifth percentile ≥0.95 against identically encoded unwatermarked exports, plus no conspicuous artifacts in review | Objective report and blinded visual inspection |
| Photo finalization | Proposed p95 ≤2 seconds on named reference phones | On-device timing; feasibility gate establishes whether the target is achievable |
| Privacy | No default upload of media, perceptual descriptors, faces, or exact location; no public stable device identity | Network traffic audit and public-record inspection |
| Durability | No unexplained media loss in interruption/restart tests; registration state reflects server acknowledgement | Crash, storage, queue, and outage test results |

Evaluate recovery and quality per supported device and transformation rather than hiding failures in averages. Narrowing an envelope requires an explicit documented product decision before pilot release. Exact-integrity correctness and prohibited-data-leakage gates cannot be relaxed to improve recovery.

Product observations such as time to first successful capture, reviewer completion rate, and abandonment can be collected through consented pilot sessions. They are exploratory measures until baseline data exists; do not introduce identifying analytics or raw-media collection just to populate a dashboard.

## Working scope and boundaries

The pilot includes Android in-app JPEG capture, an invisible public record identifier, strict file/pixel integrity checks, signed records, local Android verification, offline queuing, safe sharing, and record management/recovery. Location is off by default; capture and public verification do not require a user account. Installation enrollment still supports authenticated issuance.

Conventional watermarking is evaluated first. Learned watermark models are considered only if measured benefit justifies their cost and complexity. No model, payload redesign, device list, or robustness promise is selected by this brief.

iPhone, video/audio, browser verification, authenticated video excerpts, editing/derivative records, and manufacturer integration are deferred. This is a staged pilot, not completion of the original specification's full first-release scope.

## Step 1 completion and next decisions

The pilot audience, product problem, four core journeys, claim vocabulary, success metrics, and success/failure examples are established above as the project's working baseline. They are product decisions made under the request to proceed, not claims of stakeholder research or security validation.

Step 2 must name reference devices, minimum Android support, accountable owners, free-resource constraints, and the detailed pilot scope. Subsequent gates determine feasibility, threat/assurance policy details, protocol formats, and implementation. No spending, deployment, or release date is authorized or promised by this document.

The no-cost constraint and revised device/distribution scope in [step 2](02-pilot-scope-and-free-development.md) govern implementation. No paid hardware, compute, hosting, datasets, or store enrollment is planned.
