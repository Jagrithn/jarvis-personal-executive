# Limits and risks

- This is a local development app, not a hardened multi-user service or an OS sandbox. Fixed capability adapters and path checks constrain requested operations; malicious processes already running as the same user are outside this release's threat model. No untrusted plugins or generated code may be loaded. Local model output is only an untrusted action proposal.
- Existing Python and repository paths are captured at build time. Rebuild after moving them. Signing is ad-hoc and the app is not notarized.
- Application verification proves that the requested bundle is running, not that a specific Finder window opened or an app is responsive. Cancellation does not close applications or delete completed sample files.
- Cancellation is cooperative and bounded for subprocesses; filesystem calls are short synchronous operations and can complete before cancellation is observed. Evidence and partial results remain visible.
- Runtime state is local SQLite, not encrypted by this app. OS account/FileVault controls apply. New service files use a private umask. No secrets are stored in task records by the built-in commands.
- Directory listings expose names, not contents; all directory entries including symlinks are listed without following them. External workspace modifications during verification can cause an honest failed check. Concurrent hostile filesystem replacement by the same OS user is not a sandbox guarantee.
- History is loaded into memory and polled in full. Pagination/retention is a future requirement for large histories. The single-app lifecycle is the supported usage; manually running multiple backends against the same data directory is not supported.
- Local model inference is now implemented; model downloads require network access during setup. Voice, arbitrary desktop automation, background login startup, and new privilege grants are not implemented. Restart does not resume unfinished work or persist the dispatch pause flag.
