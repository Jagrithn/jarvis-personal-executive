# Local workflow and fixed-worker foundations

## Phase 5 public research report increment — 16 November

`research TOPIC and save a report` is now a cross-domain workflow: JARVIS opens a Chrome search, reads up to three public result articles through the bounded browser reader, summarizes their text with the local model, writes a new Markdown report in the demo workspace, and independently reads the saved bytes back. The report includes URLs, article-text hashes, bounded excerpts, and an explicit warning that model claims are not independently fact-checked. It does not message anyone or post online. The command routes separately from `research TOPIC`, which still shows an unsaved answer.

Focused tests cover routing, successful artifact and evidence, and tampering rejection. A live app request for black holes succeeded with two article URLs and a saved 1,769-byte report whose SHA-256 matched the app's independent receipt. The live run took about 25 seconds, so this is a functional milestone rather than a speed improvement. Google and source availability can change; a failed fetch leaves no false success claim. Broader Phase 5 worker contracts remain unfinished.

These adapters provide bounded Phase 5/6 foundations. They do not complete the broader phases: there is no generated worker code, background daemon, outbound communication, or autonomous tool selection. OpenCode and browser research have separate bounded paths elsewhere in this project.

## Phase 6 worker registration trial — 16 November

Registration now runs the chosen fixed template in a disposable workspace before changing the registry. The trial checks that a normal note produces a verified artifact, a symlink to an outside sentinel is excluded, and a changed artifact fails independent verification. A failed trial prevents registration. The trial result is attached to the task and rechecked by the verifier. This is a narrow evaluation gate for the two existing templates; it is not a general agent factory or a proof that generated code is safe. The owner approval gate remains in the executive before registration.

## Routing and approval contract

`execute_workflow(capability, command, root, cancel)` executes a scoped command and returns a JSON-serializable result. `verify_workflow(capability, result, root)` independently reopens the artifact and its sources (or SQLite registry) and returns evidence or raises. `root` is the existing executive workspace; registry storage is its parent data directory.

| Capability | Accepted command | Effect |
| --- | --- | --- |
| `workflows.report` | `create research report` | New Markdown report quoting workspace notes |
| `workflows.draft` | `draft workspace summary` | New Markdown communication draft; never sent |
| `workflows.organize` | `plan file organization` | New JSON proposal; no file moved |
| `workers.list` | `list workers` | Read registered fixed templates |
| `workers.register` | `register worker: research-reporter` or `register worker: file-organizer` | Persist approved template and registration audit |
| `workers.run` | `run worker: research-reporter` or `run worker: file-organizer` | Run the registered report or organization template |

The caller must route and authorize capabilities and obtain explicit owner approval **before invoking `workers.register`**. This low-level adapter cannot infer approval from command text. Every registration increments a revision and records a new audit event. A run requires a registered name, exact fixed capability mapping, template version 1 and matching audit row. Registering other names or executable content is rejected. Workers gain no capabilities beyond these templates.

## Source and artifact boundaries

Only top-level regular UTF-8 `.txt`/`.md` notes are included, with the same bounds as the knowledge reader: 100 notes, 64 KiB each, 2 MiB total. Symlinks, subdirectories, other formats and names beginning `jarvis-` are excluded. That prefix is reserved for generated output. Reports quote up to 2,000 characters per note, identify source filenames and full-content SHA-256 hashes, and explicitly report insufficient evidence for an empty workspace. This is a source digest, not an externally researched or model-synthesized report. The draft uses the same quoted evidence under a communication-draft heading. Organization proposals cover eligible notes only and suggest `notes/<original-name>` without applying changes.

Artifacts have unique `jarvis-<workflow>-<uuid>.md` or `.json` filenames and mode 0600. Writes use a directory descriptor, `O_EXCL` and `O_NOFOLLOW`; no original is overwritten. Verification validates the capability/name scope, independently reads the artifact, regenerates the deterministic output from current notes, compares full artifact bytes and hashes, and checks each source hash. Evidence does not claim factual accuracy of source statements. Source changes invalidate verification.

Cancellation is checked before work, after source reading, before writes, and before registry replacement. Effects completed before cancellation remain; a cancelled task must not imply rollback.

## Registry persistence

`data/workers.sqlite3` uses schema version 1 and records template version, registration revision and timestamped audit entries. There are only two approved templates and a maximum of 1,000 registrations. Reads are bounded to 4 MiB. SQLite operates on an in-memory database deserialized from a no-follow regular-file read; persistence writes a unique mode-0600 staged file and atomically replaces the registry using directory descriptors. SQLite never opens an uncontrolled filesystem path or executes generated code.

The registry lock protects threads in a **single executive process**. Multiple executive writers are unsupported; deployment must keep a single owning process. Registry integrity/read-back checks are not a security boundary against another process that already has write access to the user's data directory. Existing schema versions other than 1 are rejected, with no automatic migration.

## Validation

`python3 -m unittest discover -s tests -p test_workflows.py` covers real temporary-directory fixtures: report/draft/manifest artifacts, independent tamper and source-change detection, repeat-run uniqueness, restrictive file modes, read-only workspace failure, cancellation before and between operations, symlink/escape rejection, unsupported worker names, registry restart and revision persistence. Full integration additionally depends on caller routing, approval, lifecycle and verifier dispatch tests.


## Durable schedules (host-driven)

`Scheduler(data)` loads `data/schedules.sqlite3` and pauses every previously active schedule. It does not create a process, thread, timer, login item, or launch agent. The host calls `tick(submit, lookup)` from its existing executive loop and must skip dispatch while stopped or closing. Creation and resume require explicit owner approval at the caller boundary.

- `create(worker, interval)` validates the registered fixed worker and integer interval (60–86,400 seconds), creates an active record and returns it. First due time is now plus interval.
- `list()` returns persisted schedule dictionaries with `id`, `worker`, `interval`, `state`, `next_due`, `inflight`, `task_id`, and `last_error`.
- `cancel(id)` permanently cancels that schedule and returns the record; cancellation does not itself cancel an already submitted task. The host should use its normal task-stop API for that.
- `pause_all()` pauses active schedules and retains any in-flight task association. Stop-all must call this in addition to cancelling executive tasks.
- `resume_all()` validates paused workers, activates their schedules and resets due time to now plus interval. Live in-flight tasks remain associated, so resuming cannot overlap them. Only records loaded as in-flight during process startup are considered restart orphans and cleared upon explicit approved resume. The host must ensure the prior executive process is gone before restarting.
- `tick(submit, lookup)` passes `{'command': 'run worker: NAME'}` to `submit`, expecting a task dictionary with a nonempty string `id`. `lookup(id)` returns the current task dictionary or `None`. Recognized terminal states are `succeeded`, `failed`, `cancelled`, and `interrupted`; missing or unknown tasks remain blocked. It returns dispatch records containing `schedule_id` and `task_id`, or an `error`.
- `verify_persisted()` independently deserializes the on-disk database, checks schema and every schedule field against current state, and returns the verified row count. A mismatch raises.
- `close()` closes the in-memory database and is idempotent. Call after the executive worker loop stops.

Each occurrence is reserved durably before submission; due time advances to now plus interval, so missed intervals are not replayed. There is no retry and at most one in-flight task per schedule. An ambiguous submission failure pauses the schedule while retaining its reservation. An immediate resume cannot clear that reservation because a task might already have been queued. Cancel the schedule after reviewing task state, or restart the stopped executive and explicitly resume; there is no automatic recovery that could replay an unknown effect. A crash between reservation and submission can skip an occurrence by design.

There are at most 10 non-cancelled schedules and 1,000 lifetime records. Persistence uses the same bounded no-follow read and unique-file/atomic-replace discipline as workers; schema version is 1. One executive process owns the directory. Wall-clock changes can delay or advance when a schedule becomes due; this does not provide real-time scheduling guarantees. The dispatcher rechecks worker registration on every due occurrence and pauses if it is no longer valid.

For a forget/reset flow, first pause schedules and stop the worker loop, then close the scheduler before deleting its database. Recreate `Scheduler(data)` only after that cleanup. Do not keep an old in-memory Scheduler alive after deleting the database, because its next mutation would persist the old records again.

Scheduler validation: `python3 -m unittest discover -s tests -p test_scheduler.py` covers interval/worker bounds, durable restart pause, explicit resume, live-task overlap prevention, unknown tasks, missed intervals, ambiguous submission reservations, cancellation, dispatch-time registry validation and database symlink rejection.
