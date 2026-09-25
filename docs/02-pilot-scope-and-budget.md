# Step 2: Android pilot scope and feasibility budget

Date: September 25, 2026  
Status: Planning baseline frozen. Device acquisition, expenditure, benchmarks, and release approval remain pending.

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
| Distribution | Development builds and Play closed testing, followed by controlled pilot rollout after gates | Unrestricted public launch before pilot evaluation |

The export cap is an engineering scope choice, not measured evidence that watermark targets can be achieved at that size. Original working data stays protected and temporary. File-size/dimension limits for verification and temporary-data cleanup are specified at the parser/privacy design steps. Do not silently discard a user's only recoverable capture.

## Android support policy

- Minimum pilot OS: Android 14 (API 34). Native production ABI: arm64-v8a. Use emulators for functional coverage, never as evidence of physical camera performance or device assurance.
- Reference hardware has at least 4 GB RAM and uses stock supported firmware. Rooted, modified, and emulated environments remain adversarial test cases, not positive capture-assurance references.
- Record the exact model/SKU, RAM, SoC, OS build, security patch, app version, and available integrity/key protection on every test run. Never infer hardware-backed keys or attestation success from a marketing name.
- Qualify each actual device/OS combination before calling it supported. Android 14 is the implementation floor, not a claim that every Android 14 phone is supported. Run minimum-API functional tests separately if acquired reference phones have newer firmware; do not downgrade security patches merely to match a test label.
- Select compile/target SDK against current stable tooling and Google Play requirements at project setup and recheck before release. A minimum OS is distinct from a store target-SDK requirement.

## Reference-device shortlist

These are selected test targets, not devices confirmed owned or purchased. Borrow existing hardware first. Regional variants are not interchangeable for a published benchmark.

| Tier | Reference configuration | Purpose | Acquisition ceiling (USD) |
| --- | --- | --- | ---: |
| Entry | Samsung Galaxy A15 5G, 4 GB / 128 GB; prefer US unlocked SKU | Memory pressure, slower processing, Samsung capture behavior | 200 |
| Middle | Google Pixel 8a, 8 GB / 128 GB, unlocked | Google camera/OS path and midrange performance | 350 |
| Upper | Samsung Galaxy S24, 8 GB / 128 GB, US unlocked variant | Higher-performance Samsung comparison | 450 |

A15 configuration is documented in [Samsung's US specification sheet](https://image-us.samsung.com/SamsungUS/samsungbusiness/mobile/phones/galaxy-a/HHP449741_A15_5G_Spec_Sheet.pdf); Pixel configuration in [Google's hardware specifications](https://support.google.com/pixelphone/answer/7158570?hl=en); S24 configuration in [Samsung's US series specification sheet](https://images.samsung.com/is/content/samsung/assets/us/2401/business/mobile/phones/galaxy/Galaxy_S24_Series_B2B_Spec_Sheet.pdf). Sources consulted September 25, 2026. Prices above are procurement limits, not current seller quotes or availability claims.

Use another model only through a documented amendment that preserves the entry/middle/upper coverage and identifies the exact replacement. Device availability cannot silently remove the low-memory test tier. Hardware purchase and physical access are prerequisites to completing goal 7, not to beginning local experiments.

## Feasibility budget

Adopt a **USD 2,000 external-cost planning ceiling through goal 7**. This is a proposed allocation, not authorization to spend or a production operating budget. Current authorized expenditure from this plan is **$0**; free/local work can proceed. Request actual expenditure only with a concrete item or service, price, purpose, and remaining balance.

| Category | Ceiling (USD) | Purpose |
| --- | ---: | --- |
| Three reference phones | 1,000 | Entry $200 + middle $350 + upper $450; borrow first |
| Accessories, shipping, and tax | 200 | Cables, power, physical test setup, and procurement overhead |
| Test data and licensing | 200 | Rights-cleared corpus gaps; prefer suitably licensed or consented data |
| Compute | 200 | Bounded benchmark runs if local resources are insufficient |
| Test services | 100 | Temporary staging/device services only if necessary for feasibility |
| Contingency | 300 | Unexpected feasibility costs; no automatic authority to consume |
| **Total** | **2,000** | **Cash ceiling for the feasibility phase only** |

Developer time, existing computer use, participant recruitment, later pilot incentives, external security review, store enrollment, and production operations are excluded and not valued at zero. Before proceeding beyond feasibility, create the implementation/release budget with labor and ongoing service costs. Unspent hardware allocation stays unspent unless explicitly reassigned. Do not enable unlimited cloud billing or paid automatic renewals.

## Responsibility assignments

| Decision or workstream | Accountable owner | Execution / required evidence |
| --- | --- | --- |
| Scope, budget, tradeoffs, participant recruitment | Armaan Singh | Review changes and provide recruitment/device access; no spending assumed |
| Product and engineering documents | Armaan Singh | Codex prepares versioned decisions and acceptance criteria |
| Watermark experiments and protocol/mobile/backend implementation | Armaan Singh | Codex implements when tasked; Armaan supplies physical-device runs/access where remote tools cannot |
| Dataset rights and privacy decisions | Armaan Singh | Record sources/consent and policy; Codex assists with inventory and checks |
| QA and security gate tracking | Armaan Singh | Reproducible test reports; independent reviewer to be appointed before release security sign-off |
| Production accounts, credentials, release, and support | Armaan Singh | Name any replacement operator before production deployment; do not assume Codex provides continuous monitoring |

This assigns accountability without inventing a staffed team. The independent reviewer and physical-device access are explicit later prerequisites. If the project owner changes, update this table before delegating credentials or release authority.

## Feasibility acceptance and sequencing

1. Goals 3–4 define the threat/privacy policy and user experience within this scope.
2. Goal 5 builds a reproducible harness, a separate tuning set, and a frozen evaluation plan. Final release evaluation still requires at least 1,000 held-out photos and 300,000 unmarked inputs under the original spec.
3. Goal 6 benchmarks conventional watermark candidates first. Assess net payload, screenshot/crop recovery, visual quality, latency, memory, and code/license suitability.
4. Goal 7 compares measured options on all three named device tiers. If conventional candidates miss the required envelope, evaluate learned alternatives before narrowing scope or committing to implementation.
5. Exit feasibility with a pinned candidate, payload analysis, device measurements, declared recovery envelope, license decision, and explicit go/no-go record. Do not treat initial tuning results as final release validation.

Carry forward the spec's strict integrity/privacy gates and photo recovery targets, including screenshots at 512 and 1024+ pixels. A 2048-pixel export does not eliminate lower-resolution recovery testing. Proposed device targets remain photo finalization p95 ≤2 seconds and incremental peak memory <512 MB. If these fail, document the tradeoff; do not quietly change a requirement or hide a failing tier in an average.

If no candidate provides useful screenshot recovery within acceptable visual quality and cost, stop the watermark-dependent release and present the measured options. Exact-file verification may remain technically useful but is a separate product-scope decision, not an automatic substitute.

## Completion record

Step 2 planning deliverables are complete: the pilot boundary, minimum OS, three reference-device configurations, accountable owner, spending proposal, deferrals, and feasibility exit criteria are recorded. No hardware access, purchase approval, measurements, staffing commitment, or deployment is claimed. Goal 3 is next. Step 2's requirement to approve spending before purchases remains enforced whenever an actual purchase is proposed.
