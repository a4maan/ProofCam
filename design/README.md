# ProofCam experience prototype

Open `prototype.html` in a local browser, keeping `prototype.css` and `prototype.js` beside it. No build, package installation, server, or paid tool is required. GitHub's file view shows source; download the three files or clone the repository to interact with it.

Use the left-hand scenario selectors, then the app controls. Start with Enable camera → Take photo → registration disclosure → Take photo → Finish processing. The captured asset is a single in-memory sample; another capture replaces it. Reset clears the example state. Verification has 15 selectable outcomes.

Everything is simulated. The prototype makes no network requests, opens no real picker/camera/share sheet, accepts no credentials or files, and stores nothing. The Content Security Policy blocks network connections and external dependencies. It is a design artifact, not the Android application or an integrity verifier.

The [screen specification](../docs/04-capture-and-verification-design.md) defines production behavior, transitions, accessibility requirements, and review exercises. Some production flows (editable crop regions, admission, OS permissions, durable queues, secret storage) are specified but simulated here.

Validation: JavaScript syntax checked with Node; 33 assertions using a stub DOM covered trust-gated result styling, all 15 result scenarios, pending-state sharing, rejection behavior, expired-challenge downgrade, pause/resume, local versus public deletion, digest refusal, crop scope, and storage preservation. These checks are not browser rendering tests. Visual browser review, native accessibility testing, and user comprehension evaluation remain pending.
