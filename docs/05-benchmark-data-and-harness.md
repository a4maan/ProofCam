# Step 5: Benchmark data and test harness

Date: September 25, 2026

Status: Harness, expanded acquisition, review tooling, and screenshot intake delivered; full corpus readiness **in progress**.

## Delivered

- A local Python harness with pinned dependencies, bounded image inputs, deterministic preprocessing and 29 transforms, run fingerprints, candidate-output manifests, strict prediction validation, quality metrics, and per-transform/device/size reports.
- 1,200 locally downloaded Open Images source files: **100 tuning, 1,000 reserved held-out, 100 negative candidates**. Different author groups are assigned to separate splits; one image per author is selected. Byte/decoded-pixel duplicates were excluded. The manifest is content-locked and records download exclusions.
- Continuation: **10,000 additional negative-source candidates** are now downloaded and locked, bringing the distinct-source total to **11,200** (100 tuning, 1,000 held-out, 10,100 negative). A separate supplement contains **53 native 2048+ resolution variants** of starter sources: 9 tuning, 42 held-out, and 2 negative; variants are not extra independent images.
- A code/source-pinned **300,000-case negative stress plan** (30 variants of each of the 10,000 additional sources), with streaming generation and a 120-case materialized sample. This is a recipe count, not 300,000 independent natural photographs or completed evaluations.
- Per-image title, author, source URL, dataset-declared CC BY 2.0 license, dimensions, and hashes in the committed inventory. Open Images documents these fields and official subset downloads in its [download guide](https://storage.googleapis.com/openimages/web/download_v7.html). Individual rights and content review is still pending.
- A screenshot-intake schema and validator for actual captures, a candidate metadata template, and a tested scoring contract that keeps unsuccessful and missing cases in the denominator.
- An end-to-end tuning smoke run; no watermark model or production verifier is claimed. Downloaded media, metadata caches, and generated runs stay local and are ignored by Git.

See [benchmark instructions](../benchmark/README.md), [continuation tooling](../benchmark/READINESS.md), the [starter audit](../benchmark/reports/corpus-audit.json), [expanded screening](../benchmark/reports/expanded-screening.json), and [continuation validation](../benchmark/reports/step05-continuation.json). No paid data, compute, hardware, hosting, or services were used.

## Dataset separation and freeze policy

`openimages-starter.jsonl` is a byte-locked **starter snapshot**, not the final evaluation freeze. Its 1,000 held-out images have not been used to select a watermark or thresholds. Downloader validation and inventory hashing are data checks, not model evaluation. Use only the tuning split for candidate development.

Author grouping is a practical contamination precaution, not proof of scene/photographer independence. Before final freeze, review near-duplicates, derivative copies, synthetic/non-photo content, sensitive content, permission/rights, and the categories below. Do not silently edit the snapshot or swap failures to improve a candidate's score. Corrections require a new version with reasons, preserved split grouping, and a new content lock.

Once candidate code, weights, payload/ECC, thresholds, and search limits are frozen, create a separate release-evaluation lock identifying the approved corpus, device matrix, transformations, candidate manifest, and protocol versions. `--allow-heldout` merely permits a command; it does not establish that this review occurred.

## Coverage to review before release

| Required area | Current state | Completion evidence |
| --- | --- | --- |
| At least 1,000 held-out varied photos | 1,000 reserved downloaded candidates | Approved content/rights inventory and source-disjoint release lock |
| Low texture, text, faces, night scenes, gradients, extreme aspect ratios | Dataset human annotations identify held-out faces (78), text (17), night (5), darkness (10), and panorama (1); automated screening flags review candidates; local review pending | Category labels and denominators; no favorable aggregate hides a weak category |
| Motion-related image difficulty | Unreviewed still-photo candidates | Motion blur and moving subjects tagged in the photo corpus; video remains outside this pilot |
| Tuning separation | 100 sources, author-disjoint from held-out and negative pools | Locked source/author/byte checks; near-duplicate review |
| Negative inputs | 10,100 natural-source candidates downloaded; 300,000 correlated stress recipes pinned for the 10,000-source expansion; 120 generated/checked | Validate unmarked status, distinct-byte counts and source diversity before final QA3; no pooled independent-sample bound from correlated variants |
| Native 2048-pixel cases | 53 original-resolution variants verified against upstream version digests; two tuning originals exercised across 58 cases | Expand resolution coverage if the final matrix needs more sources; source CDN throttling/failed URLs are recorded; never upscale to manufacture eligibility |
| Real screenshots | No physical evidence collected; strict importer implemented and tested | Actual Android/iPhone/desktop screenshot files linked to parent watermarked exports, with device/app/scale/media-size metadata |
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
2. Approve negative eligibility and evaluate distinct inputs across the pinned stress suite; supplement independent natural-source diversity as needed. The 300,000 recipe count alone does not satisfy an independent-input statistical claim. No decoder has been evaluated.
3. Review the 53 original-resolution variants and decide whether each final device/transform bucket has adequate coverage. Resume additional original-source acquisition only when the source permits it; do not bypass throttling.
4. Collect actual screenshots on freely available devices after a candidate embeds the target IDs; retain the intake metadata and untouched screenshot bytes.
5. Freeze the final corpus and candidate/search configuration before release evaluation. Record any support-envelope change if required resources are unavailable.

Goal 6 can begin conventional watermark experiments on the 100 tuning images now, while corpus review and expansion continue. No user media needs to be uploaded, and no measurement in this step establishes screenshot robustness, production security, or mobile performance.

## Continuation validation

All **34 tests** pass. The expanded screening checked hashes/attribution fields on all 11,200 distinct sources and found zero candidate pairs at its chosen combined dHash/pHash thresholds; this does not prove all near-duplicates absent. No image was automatically approved. Perceptual fingerprints remain local and never feed integrity results.

A 120-case negative sample had 120 distinct byte hashes, and a replay reproduced the checked output hashes. Two native 2048-pixel tuning sources generated 58 checked cases. Confidence intervals are suppressed for repeated source groups or byte-identical inputs within a bucket. Screenshot results separate capture device, display scale, and region-selection mode.

The [category coverage report](../benchmark/reports/category-coverage-v1/summary.json) preserves the provenance of imported dataset human labels. Absence of an annotation means unknown. It does not imply absence of faces/text or replace license, consent, category, or scene review. Source annotation files and vocabulary hashes are recorded.

A paginated local review tool is available at `benchmark/data/review-expanded-v1/index.html`. Reviewers can export decisions without network access or silently modifying frozen manifests. Physical screenshot collection remains dependent on available devices and candidate watermarked exports; neither is fabricated by the harness.

## Tuning content review continuation

AI visual screening now covers all 100 tuning sources; three ambiguous examples also received source-resolution inspection. The [review decisions](../benchmark/reviews/tuning-visual-v1.json) recommend 92 primary-photo candidates and eight separately tracked stress examples. Five visible marks/date stamps were observed. These recommendations preserve the original locked sources and splits and do not approve licenses or certify absence of watermarks.

The review validator checks completeness, unique decisions, source hashes, tuning-only scope, and the explicit absence of release/rights approval. Its [report](../benchmark/reports/tuning-visual-v1.json) pins the review and source manifest. Held-out/negative visual review, rights review, and actual screenshot evidence remain outstanding; goal 5 is still In progress.
