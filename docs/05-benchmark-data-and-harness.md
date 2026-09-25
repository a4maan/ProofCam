# Step 5: Benchmark data and test harness

Date: September 25, 2026

Status: Harness and starter acquisition delivered; full corpus readiness **in progress**.

## Delivered

- A local Python harness with pinned dependencies, bounded image inputs, deterministic preprocessing and 29 transforms, run fingerprints, candidate-output manifests, strict prediction validation, quality metrics, and per-transform/device/size reports.
- 1,200 locally downloaded Open Images source files: **100 tuning, 1,000 reserved held-out, 100 negative candidates**. Different author groups are assigned to separate splits; one image per author is selected. Byte/decoded-pixel duplicates were excluded. The manifest is content-locked and records download exclusions.
- Per-image title, author, source URL, dataset-declared CC BY 2.0 license, dimensions, and hashes in the committed inventory. Open Images documents these fields and official subset downloads in its [download guide](https://storage.googleapis.com/openimages/web/download_v7.html). Individual rights and content review is still pending.
- A screenshot-intake schema for actual captures, a candidate metadata template, and a tested scoring contract that keeps unsuccessful and missing cases in the denominator.
- An end-to-end tuning smoke run; no watermark model or production verifier is claimed. Downloaded media, metadata caches, and generated runs stay local and are ignored by Git.

See [benchmark instructions](../benchmark/README.md), [corpus audit](../benchmark/reports/corpus-audit.json), and [smoke report](../benchmark/reports/harness-smoke.json). No paid data, compute, hardware, hosting, or services were used.

## Dataset separation and freeze policy

`openimages-starter.jsonl` is a byte-locked **starter snapshot**, not the final evaluation freeze. Its 1,000 held-out images have not been used to select a watermark or thresholds. Downloader validation and inventory hashing are data checks, not model evaluation. Use only the tuning split for candidate development.

Author grouping is a practical contamination precaution, not proof of scene/photographer independence. Before final freeze, review near-duplicates, derivative copies, synthetic/non-photo content, sensitive content, permission/rights, and the categories below. Do not silently edit the snapshot or swap failures to improve a candidate's score. Corrections require a new version with reasons, preserved split grouping, and a new content lock.

Once candidate code, weights, payload/ECC, thresholds, and search limits are frozen, create a separate release-evaluation lock identifying the approved corpus, device matrix, transformations, candidate manifest, and protocol versions. `--allow-heldout` merely permits a command; it does not establish that this review occurred.

## Coverage to review before release

| Required area | Current state | Completion evidence |
| --- | --- | --- |
| At least 1,000 held-out varied photos | 1,000 reserved downloaded candidates | Approved content/rights inventory and source-disjoint release lock |
| Low texture, text, faces, night scenes, gradients, extreme aspect ratios | Source images acquired; tags not manually reviewed | Category labels and denominators; no favorable aggregate hides a weak category |
| Motion-related image difficulty | Unreviewed still-photo candidates | Motion blur and moving subjects tagged in the photo corpus; video remains outside this pilot |
| Tuning separation | 100 sources, author-disjoint from held-out and negative pools | Locked source/author/byte checks; near-duplicate review |
| Negative inputs | 100 candidates downloaded, no ProofCam watermark added | Validate candidate-specific unmarked status and grow to at least 300,000 eligible inputs for final QA3 |
| Native 2048-pixel cases | Downloaded CVDF copies have long edges of 768–1024 pixels; 1,187 are at least 1024 | Acquire freely licensed higher-resolution sources or qualified device captures; do not upscale to manufacture eligibility |
| Real screenshots | None collected | Actual Android/iPhone/desktop screenshot files linked to parent watermarked exports, with device/app/scale/media-size metadata |
| Automatic and manual region selection | Only synthetic screen/crop plumbing available | Separate measured automatic-region success and recovery after actual region selection |
| Real combined edits | Synthetic chain implemented only | Actual screenshot → 75% crop → 1024 resize → pinned Q70 pipeline |
| Android timing and memory | No available physical device run yet | Exact device/OS/app/runtime records; p95 finalization/search, peak memory, energy/thermal observations |
| Candidate quality and recovery | No candidate implemented in goal 5 | Goal 6 exports, blinded quality review, complete decoder search results |
| Wrong lookup / false cryptographic acceptance | Not measured by this image harness | Protocol/verifier adversarial tests in later implementation and QA goals |

The original screenshot target includes screenshots produced on non-Android devices even though the first app is Android. Use freely available or borrowed display devices; do not synthesize evidence or buy hardware. If a device category remains unavailable, explicitly narrow the published support envelope before release rather than implying it was tested.

## Reproducibility and interpretation

Each prepared run records source and output SHA-256, dimensions, source split, actual decoder-device label, transform, synthetic-screen flag, payload ground truth when provided, environment versions, encoder settings, and harness source hash. The scorer separates file transformations, decoder devices, output-size buckets, and positive/negative/smoke inputs.

Recovering the complete expected ID alone is success; partial bits, detector score, and a result containing conflicting IDs are not. Missing/failed searches remain failures in the denominator. A zero false-detection upper bound is available only when every scheduled negative input completed the entire declared search and zero detections occurred. Confidence calculations do not turn correlated crops into independent sources.

JPEG quality numbers are pinned to the recorded encoder. Synthetic screenshot canvases are named synthetic in files and reports. Research preprocessing and pixel hashes are not the production canonicalization contract. Hardware or algorithm changes create a new recorded run; do not compare timing without its runtime/device context.

## Remaining work and roadmap status

Goal 5 remains **In progress** because its original completion criterion includes preparation of the full release evaluation data, not just a functioning harness. Remaining work is explicit:

1. Review the downloaded image rights, content categories, and near-duplicate contamination before final corpus approval.
2. Expand and approve the negative suite to 300,000 inputs using free sources, retaining source groups and distinguishing natural diversity from correlated derived inputs. The current 100-source pool does not satisfy that gate.
3. Add native higher-resolution sources for the 2048-pixel cases; these CVDF copies cannot qualify through upscaling.
4. Collect actual screenshots on freely available devices after a candidate embeds the target IDs; retain the intake metadata and untouched screenshot bytes.
5. Freeze the final corpus and candidate/search configuration before release evaluation. Record any support-envelope change if required resources are unavailable.

Goal 6 can begin conventional watermark experiments on the 100 tuning images now, while corpus review and expansion continue. No user media needs to be uploaded, and no measurement in this step establishes screenshot robustness, production security, or mobile performance.
