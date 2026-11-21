# Bounded public browser reader

The `browser.read` capability accepts `read page: https://example.com/` after executive confirmation. It returns the source URL, title, up to 20,000 characters of rendered body text, a SHA-256 of that captured text, truncation flag, HTTP status, and `scope: public-read`.

Install the isolated runtime with `scripts/setup-browser.sh`. Dependencies stay in `.runtime/browser` and Chromium binaries in `.runtime/browser-binaries`; no global Python package or existing browser profile is used. Run browser tests with `.runtime/browser/bin/python -m unittest discover -s tests -p test_browser.py -v`.

Acquisition permits only HTTP/HTTPS standard ports without URL credentials. Each destination, including redirects, must resolve entirely to public unicast IP addresses. Connections use a checked numeric address directly, while HTTPS validates the original hostname and certificate. This prevents a second DNS resolution from changing the connection target. Proxy environment settings are not used. Responses are limited to 1 MiB, six request attempts, successful HTML/plain-text responses, and uncompressed bodies. Attachments are rejected. The subprocess has a 35-second overall deadline and each socket has an eight-second timeout.

A new nonpersistent Chromium context renders the fetched document. Page JavaScript and service workers are disabled; downloads are disabled; all requests except the one locally fulfilled main document are aborted. A restrictive document content-security policy also blocks scripts, frames, forms, and external resources. No links are clicked, no forms are submitted, no login is attempted, no cookies are loaded or forwarded. The tool does not access the user's existing browser tabs or browser profile.

This is a static public-page reader. Script-dependent pages, authenticated pages, PDFs, compressed responses, and sites requiring cookies may fail or have incomplete text. Public GET requests are externally visible and a server can implement side effects even for GET; the tool cannot enforce remote server semantics. Browser background infrastructure is outside the page-request router; Chromium background networking is disabled, but this is not an OS network sandbox. Use an OS network policy for a stronger hostile-browser boundary.

Verification recomputes the text hash and validates bounds and result shape. This is capture-integrity evidence, **not independent factual verification of page claims**. Page content is untrusted source material and must never be interpreted as tool instructions.

Integration: `execute_browser(capability, command, root, cancel)` returns the result dictionary; `verify_browser(capability, result, root)` returns an evidence list. `root` is the executive workspace; its grandparent selects the project runtime so packaged app resources work correctly. Invalid requests raise `ValueError`; unavailable runtime raises `RuntimeError`; subprocess deadlines/cancellation use existing adapter semantics.

The deterministic renderer fixture supplies HTML directly to the rendering function and checks a local HTTP listener receives no image/frame requests. Production URL fetching has no private-network override. Security unit tests additionally cover private and multicast IPs, credentials, ports, mixed DNS answers, private redirects, attachments, response bounds, command scope, and text tampering.

Reference: [Playwright nonpersistent contexts](https://playwright.dev/python/docs/api/class-browser#browser-new-context) and [request routing/service-worker restrictions](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route).
