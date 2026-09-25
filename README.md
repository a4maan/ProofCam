# ProofCam

ProofCam is an Android-first camera project that lets recipients check whether a photo matches a registered export and see which capture checks passed.

This folder is the project working directory. Product documentation, application code, backend code, and project tooling will live here as development proceeds.

## Current milestone

Steps 1 and 2 are documented in the [product brief](docs/01-product-brief.md) and [pilot scope and free development](docs/02-pilot-scope-and-free-development.md). These are planning decisions; implementation and device validation remain pending.

The Android photo pilot targets Android 14+ on existing or freely borrowed hardware. Development uses free tools, local compute, and no paid services. Pilot APKs will be distributed directly; hardware support is limited to configurations actually validated.

Step 3 is defined in the [threat model, privacy rules, and assurance policy](docs/03-threat-model-and-privacy-policy.md). Security controls are specified but not yet implemented or audited.

Step 4 is documented in the [capture and verification screen design](docs/04-capture-and-verification-design.md), with a [clickable local prototype](design/prototype.html) and [opening instructions](design/README.md). All prototype behavior is simulated.

Step 5 has a working [benchmark harness](benchmark/README.md) and 1,200-source starter corpus. Its [readiness record](docs/05-benchmark-data-and-harness.md) remains **in progress**: review, actual screenshots, and the full negative corpus are still pending.

Next available work: step 6, benchmark conventional watermarks on the tuning split while completing corpus readiness.

## Planning references

- [Original engineering specification](ProofCam_Product_Spec.docx)
- [Development roadmap](ProofCam_Android_Development_Roadmap.xlsx)

The original specification describes a broader release than the initial Android photo pilot. The product brief records the staged scope and the sharing-policy adjustment agreed during planning.
