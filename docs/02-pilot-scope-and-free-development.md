# Step 2: Android pilot scope and free development

Date: September 25, 2026  
Status: Planning baseline frozen. Available-device inventory, benchmarks, and release approval remain pending.

## Decision

Deliver an invitation-only Android photo pilot for up to 20 participants, including at least 10 reviewers. Capture and review can be performed by the same participants, but comprehension is measured on at least 10 distinct people. Complete the watermark feasibility gate before setting a release date or building the full production service.

Armaan Singh is the accountable project owner by default as the repository owner and project sponsor. Codex performs implementation and documentation in the working repository when tasked; it is not an independent security reviewer or an ongoing service operator. No additional staff are assumed to have been hired.

## Frozen pilot scope

| Area | Included in the pilot | Deferred |
| --- | --- | --- |
| Capture | Native Android, rear main camera, single-shot SDR JPEG, portrait/landscape; normalized orientation and sRGB pixels | Front/auxiliary lenses, RAW, HDR exports, burst, video/audio, gallery certification |
| Export | One immutable export per capture; cap at 2048 pixels on the long edge, preserve aspect ratio, never upscale; pin JPEG encoder and quality after benchmark | Full sensor-resolution exports, user-selectable compression, editing |
| Watermark | Public random record ID embedded before final encode; conventional algorithms first; model/payload chosen at goal 7 | Mandatory AI dependency, universal survival promises |
| Registration | Per-installation signing, online challenges, server validation, signed certificates and local receipts | Manufacturer sensor certification, public arbitrary-file signing |
| Offline | Finalize and locally sign when possible, durable queue, restart recovery, pending-status sharing | Fresh-challenge claims for offline or expired sessions |
| Verification | Local Android extraction and file/pixel hashing; public record lookup; JPEG originals and JPEG/PNG screenshots; user-selected screenshot region; consented digest fallback | Browser/iOS interfaces, HEIC/RAW decoding, arbitrary document or video verification |
| Trust UI | Separate record signature, issuer, content, capture checks, and availability; versioned trust bundle and revocation behavior | Generic “real” or “AI-free” badge |
| Management | Accountless installation credentials, export/import receipts, recovery credential, authorized record removal, local deletion | Optional account linking, teams, paid subscriptions |
| Privacy | No default media uploads, no location feature or microphone permission, public records without stable device identity | Cloud photo backup, faces/descriptors in telemetry, advertising analytics |
| Distribution | Signed APKs distributed directly to invited testers at no cost, followed by controlled pilot rollout after gates | Paid store enrollment; unrestricted public launch before pilot evaluation |

The export cap is an engineering scope choice, not measured evidence that watermark targets can be achieved at that size. Original working data stays protected and temporary. File-size/dimension limits for verification and temporary-data cleanup are specified at the parser/privacy design steps. Do not silently discard a user's only recoverable capture.

## Android support policy

- Minimum pilot OS: Android 14 (API 34). Native production ABI: arm64-v8a. Use emulators for functional coverage, never as evidence of physical camera performance or device assurance.
- Reference hardware has at least 4 GB RAM and uses stock supported firmware. Rooted, modified, and emulated environments remain adversarial test cases, not positive capture-assurance references.
- Record the exact model/SKU, RAM, SoC, OS build, security patch, app version, and available integrity/key protection on every test run. Never infer hardware-backed keys or attestation success from a marketing name.
- Qualify each actual device/OS combination before calling it supported. Android 14 is the implementation floor, not a claim that every Android 14 phone is supported. Run minimum-API functional tests separately if acquired reference phones have newer firmware; do not downgrade security patches merely to match a test label.
- Select compile/target SDK against current stable tooling and Google Play requirements at project setup and recheck before release. A minimum OS is distinct from a store target-SDK requirement.

## Reference-device comparison targets

Start with Android hardware already owned or available to borrow for free. Inventory the actual devices before selecting the measured support matrix. No phone purchases are planned. Regional variants are not interchangeable for a published benchmark.

| Tier | Illustrative reference configuration | Purpose |
| --- | --- | --- |
| Entry | Samsung Galaxy A15 5G, 4 GB / 128 GB | Memory pressure, slower processing, Samsung capture behavior |
| Middle | Google Pixel 8a, 8 GB / 128 GB | Google camera/OS path and midrange performance |
| Upper | Samsung Galaxy S24, 8 GB / 128 GB, US variant | Higher-performance Samsung comparison |

These examples guide comparison; they are not mandatory acquisitions. Configuration sources: [Samsung A15 specification](https://image-us.samsung.com/SamsungUS/samsungbusiness/mobile/phones/galaxy-a/HHP449741_A15_5G_Spec_Sheet.pdf), [Google Pixel specifications](https://support.google.com/pixelphone/answer/7158570?hl=en), and [Samsung S24 specification](https://images.samsung.com/is/content/samsung/assets/us/2401/business/mobile/phones/galaxy/Galaxy_S24_Series_B2B_Spec_Sheet.pdf), consulted September 25, 2026.

Use available phones and record their exact configuration. Expand tier coverage only through free access. If only one device is available, begin feasibility there and restrict any pilot support claim to validated configurations. Unavailable tiers remain untested; emulators do not replace physical-device assurance or performance evidence. This explicitly narrows the earlier three-device prerequisite to match the no-cost constraint.

## Free-development constraint

All development and pilot work must use existing resources or resources available at no charge. There is no purchasing allocation or paid-services plan.

- Use existing or freely borrowed Android phones and computers.
- Use free development tools and appropriately licensed libraries, models, and datasets; retain license and consent records.
- Run benchmarks and development services locally by default. Do not allocate paid GPU jobs, buy datasets, or subscribe to hosted tools.
- Use existing infrastructure or genuinely free hosting only after checking its terms and limits. Do not rely on expiring paid trials, automatic paid upgrades, or billable overages.
- Distribute signed pilot APKs directly without requiring paid store enrollment. Evaluate the integrity evidence actually available for that distribution path; never claim Play-backed checks passed when they did not.
- Plan local prototype signing separately from trusted public issuance. Free operation does not waive key protection, trust separation, privacy, or security requirements. If compliant public signing/hosting is unavailable at no cost, keep that capability local or pending and clearly label development records; do not represent it as a completed public deployment.
- Seek volunteer pilot participation and review. Record any missing independent review as an unmet release prerequisite.

Implementation can proceed on available resources. If a dependency requires payment, select a free alternative or explicitly defer the affected capability. Do not introduce a new paid allocation.

## Responsibility assignments

| Decision or workstream | Accountable owner | Execution / required evidence |
| --- | --- | --- |
| Scope, free-resource constraints, tradeoffs, participant recruitment | Armaan Singh | Review changes and provide recruitment or freely available device access |
| Product and engineering documents | Armaan Singh | Codex prepares versioned decisions and acceptance criteria |
| Watermark experiments and protocol/mobile/backend implementation | Armaan Singh | Codex implements when tasked; Armaan supplies physical-device runs/access where remote tools cannot |
| Dataset rights and privacy decisions | Armaan Singh | Record sources/consent and policy; Codex assists with inventory and checks |
| QA and security gate tracking | Armaan Singh | Reproducible test reports; independent reviewer to be appointed before release security sign-off |
| Production accounts, credentials, release, and support | Armaan Singh | Name any replacement operator before production deployment; do not assume Codex provides continuous monitoring |

This assigns accountability without inventing a staffed team. The independent reviewer and access to at least one actual test device are explicit later prerequisites. If the project owner changes, update this table before delegating credentials or release authority.

## Feasibility acceptance and sequencing

1. Goals 3–4 define the threat/privacy policy and user experience within this scope.
2. Goal 5 builds a reproducible harness, a separate tuning set, and a frozen evaluation plan. Final release evaluation still requires at least 1,000 held-out photos and 300,000 unmarked inputs under the original spec.
3. Goal 6 benchmarks conventional watermark candidates first. Assess net payload, screenshot/crop recovery, visual quality, latency, memory, and code/license suitability.
4. Goal 7 compares measured options on the freely available physical devices and records any untested tiers. If conventional candidates miss the required envelope, evaluate learned alternatives before narrowing scope or committing to implementation.
5. Exit feasibility with a pinned candidate, payload analysis, device measurements, declared recovery envelope, license decision, and explicit go/no-go record. Do not treat initial tuning results as final release validation.

Carry forward the spec's strict integrity/privacy gates and photo recovery targets, including screenshots at 512 and 1024+ pixels. A 2048-pixel export does not eliminate lower-resolution recovery testing. Proposed device targets remain photo finalization p95 ≤2 seconds and incremental peak memory <512 MB. If these fail, document the tradeoff; do not quietly change a requirement or hide a failing tier in an average. Untested hardware is outside the declared pilot support matrix.

If no candidate provides useful screenshot recovery within acceptable visual quality and cost, stop the watermark-dependent release and present the measured options. Exact-file verification may remain technically useful but is a separate product-scope decision, not an automatic substitute.

## Completion record

Step 2 planning deliverables are complete: the pilot boundary, minimum OS, illustrative reference configurations, accountable owner, free-development constraint, deferrals, and feasibility exit criteria are recorded. Actual hardware inventory, measurements, independent review, and deployment remain pending. Goal 3 is next.
