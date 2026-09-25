# Corpus expansion and evidence intake

These tools continue goal 5 without using paid services or changing the starter snapshot. Read `docs/05-benchmark-data-and-harness.md` for the current completion status.

## Separate source snapshots

- `openimages-starter.jsonl`: original 100 tuning, 1,000 held-out, and 100 negative candidates.
- `openimages-negatives-v1.jsonl`: 10,000 additional natural-image candidates from previously unused author groups; all assigned to the negative split. This selection deliberately excludes every starter author group, file hash, and decoded-pixel hash. These are unreviewed natural-source candidates, not 10,000 independently certified photographs.
- `openimages-originals-v1.jsonl`: eligible original-resolution versions of starter sources. They keep the parent's split and source group. They are higher-resolution variants, not independent new subjects. Do not combine variants as separate samples in a confidence interval.

Restore the starter with `python3 -m benchmark.corpus`. For the additional negatives:

```sh
python3 -m benchmark.expand negatives --count 10000
```

This verifies/restores the locked 10,000-source snapshot if it exists. It uses the fixed public CVDF bucket and no credentials. Its local footprint is several gigabytes; source media is ignored by Git. Acquisition excludes duplicate content and records failures rather than changing the starter.

Original-resolution retrieval accepts only HTTPS Flickr image CDN URLs from the pinned source metadata, verifies the historical original MD5 as a version check, then records a SHA-256. It requires native long edge ≥2048 and respects the pilot's dimension/size caps. Historical MD5 is not used as cryptographic security. HTTP 429 stops new requests; it does not trigger alternate-host bypasses. Many historical source URLs fail or are throttled, so the supplement is incomplete. Existing locked original files are verified by `python3 -m benchmark.expand originals`; if those local files are lost, do not fabricate replacements or silently substitute current versions. A new authorized acquisition should use a separate versioned snapshot.

The public repository contains attribution and locks, not downloaded images. Dataset-declared licenses still need the review specified in goal 5. Image-level approvals are not inferred from successful downloads.

## Negative stress recipes

```sh
python3 -m benchmark.negative_suite plan benchmark/manifests/openimages-negatives-v1.jsonl \
  --out benchmark/manifests/negative-stress-v1.plan.json
python3 -m benchmark.negative_suite materialize benchmark/manifests/negative-stress-v1.plan.json \
  benchmark/manifests/openimages-negatives-v1.jsonl --start 0 --count 120 \
  --out benchmark/runs/negative-stress-sample
```

Do not re-run `plan` over an existing plan: use the existing lock or deliberately create a new version. The plan pins source order, manifest hash, generator hash, and harness hash. Any code/source mismatch requires a new plan. `iter_inputs` can stream cases for an adapter without writing the full suite to disk.

The plan schedules **30 variants × 10,000 natural sources = 300,000 test recipes**. It does not claim 300,000 downloaded, independent natural photographs, 300,000 unique byte sequences, or any completed decoder evaluations. Individual batches record identical-byte cases. De-duplicate actual inputs before reporting global distinct-input counts. Sibling variants share their parent, so a pooled `3/300000` bound would be misleading. Report outcomes per transform/device/size and disclose the actual source diversity. No release gate is passed merely by preparing this plan.

Cases cover original JPEG, five recompression qualities, three resizes, six crops, three rotations, gamma, brightness, overlay, two synthetic screen canvases, a synthetic combined chain, three blur levels, and grayscale. Synthetic screen cases stay explicitly labeled synthetic. The suite contains no generated watermark identifier. External images may already contain unrelated marks and remain subject to negative-corpus review.

The scorer suppresses confidence intervals for buckets with repeated source groups or repeated byte hashes. It also keeps screenshot capture devices, display scales, and automatic/manual region selection separate. It never pools these cases into one flattering result.

## Review the data locally

```sh
python3 -m benchmark.review benchmark/manifests/openimages-starter.jsonl \
  benchmark/manifests/openimages-negatives-v1.jsonl \
  --out benchmark/data/review-expanded-v1 --summary benchmark/reports/expanded-screening.json
```

Open `benchmark/data/review-expanded-v1/index.html` locally. Each page has at most 200 images. Check the source's rights, content suitability, required categories, and duplicate flags. Add decisions, tags, and reviewer identity, then export that page's decision file before leaving it. Entries remain unreviewed until a reviewer actually changes them. No network request, upload, or automatic approval occurs. Reloading discards unsaved edits.

The scan verifies source file hashes and computes local dHash/pHash review hints. It flags possible duplicates at dHash ≤8 and pHash ≤6 bits, excluding expected resolution variants of the same source. No flag means only that this heuristic found nothing. It also flags dark, low-entropy, and extreme-aspect-ratio candidates; these are not verified night/texture/category labels. Perceptual hashes must never be used for integrity results. Detailed fingerprints and thumbnails remain in the ignored local data directory.

Review output does not rewrite a locked source manifest. Reconcile exported decisions, exclusions, and needed replacements into a new corpus version before final freeze. Keep reviewer details private if they identify pilot participants; commit only approved aggregate findings.

## Actual screenshots

Populate `benchmark/screenshot-intake.csv` only with real screenshot evidence. The media rectangle must be in bounds and match the declared media long edge. Keep the parent source split; provide the parent candidate's final export manifest and expected record ID. Record `evidence_kind=actual_device` and `actual_os_screenshot=true` only for actual device screenshots, never procedural canvases, browser mockups, or unit-test fixtures.

```sh
python3 -m benchmark.screenshots benchmark/screenshot-intake.csv \
  --sources benchmark/manifests/openimages-starter.jsonl --exports path/to/candidate-exports.jsonl \
  --out benchmark/runs/actual-screenshots --device actual-decoder-device
```

The importer refuses empty/unreviewed intake, synthetic declarations, changed hashes, wrong parent IDs, crossed splits, invalid rectangles, and unsupported sizes/formats. It verifies referenced parent export bytes and preserves complete screenshot bytes. The rectangle is a recovery hint only: it must never change what file is hashed for full integrity. Held-out input requires explicit `--allow-heldout` after evaluation freeze.

Metadata remains operator-attested; the tool does not prove that the operator used the stated device. Actual screenshots cannot test watermark recovery until a candidate embeds IDs. The blank CSV and test fixtures are not screenshot evidence. Available Android devices and the relevant OS/app versions still need to be supplied before physical collection can proceed.

## Dataset human-label coverage

`coverage.py` imports positive human-label annotations from the official Open Images V7 files and preserves their input hashes. It ignores machine rows, leaves missing annotations unknown, and flags contradictory annotations instead of choosing the favorable one. The current summary is in `reports/category-coverage-v1/summary.json`. No local reviewer approval or watermark evaluation is inferred from a dataset label.

```sh
python3 -m benchmark.coverage benchmark/manifests/openimages-starter.jsonl \
  benchmark/manifests/openimages-negatives-v1.jsonl \
  --labels benchmark/data/source-metadata/oidv7-val-annotations-human-imagelabels.csv \
  --classes benchmark/data/source-metadata/oidv7-class-descriptions.csv \
  --out benchmark/reports/category-coverage-new-version
```

The source URLs are recorded in the report and listed by the [official download guide](https://storage.googleapis.com/openimages/web/download_v7.html). Fetch those free CSVs into the indicated local metadata directory before reproducing the coverage import. Faces/text/night tags come from the dataset; low texture, gradients, motion blur, and final category approval remain local-review work.

## Recorded tuning visual review

[The versioned review](reviews/tuning-visual-v1.json) records AI visual screening of all 100 tuning sources, using contact sheets with three source-resolution spot checks. It recommends 92 primary-photo candidates and eight separate stress examples: three processed/bordered photos, two artwork scenes, one collage, one magazine cover, and one rendered graphic. Five sources have observed visible marks or date stamps; that count is not an exhaustive watermark audit. Missing tags mean unknown.

Validate the complete review against the frozen manifest and individual source hashes:

```sh
python3 -m benchmark.visual_review benchmark/manifests/openimages-starter.jsonl \
  benchmark/reviews/tuning-visual-v1.json
```

The validator rejects incomplete reviews, duplicate decisions, changed source references, cross-split decisions, and approval claims. It verifies the sidecar's references against the locked manifest; use the existing corpus audit to verify local media bytes. The [summary](reports/tuning-visual-v1.json) pins both inputs. Recommendations do not automatically filter harness runs: select a separately versioned cohort when preparing experiments. The source snapshots and existing negative stress plan remain unchanged. No rights approval, human review, authenticity determination, or held-out visual review is claimed.
