# 26 — Preserve a future async path

Accepted architectural constraint, 1 October 2026: deliver the synchronous core
now, but prefer choices that make a future native async implementation easier.
Record any choice that blocks or materially complicates that transition before
adopting it. This is not authorization to implement async now or a claim that
the current runtime is async-safe.

## Review rule

For changes to execution, context, connections, hooks or cleanup, record:

- The synchronous requirement and the concrete implementation choice.
- Whether it is reusable, needs an async counterpart, or conflicts with task
  isolation/cancellation. Distinguish implementation work from public API breaks.
- The alternative considered, why it is simpler or more costly, and migration
  work or compatibility constraints introduced by the chosen approach.
- The tests needed to establish ownership, cleanup and failure behavior.

Prefer the simpler portable choice when it satisfies the synchronous contract.
Do not silently accept a new public contract that requires thread identity,
blocking I/O inside property access, or process-global request state. If a
necessary choice obstructs async, identify it explicitly with its tradeoff.
No extra public session abstraction, generic scheduler or speculative pool is
required by this principle.

## Current inventory

| Area | Current choice / evidence | Async consequence and preferred direction |
|---|---|---|
| Model/compiler | Resolved metadata and query compilation are separated from driver execution. | Reuse declarations and compilation; keep ordinary inspection/compilation free of database I/O. |
| Request environment | `ApplicationEnvironment` uses `threading.local`; `currentEnv` is a live mutable dict. | Centralize context access. A task-context implementation can use `ContextVar`, but must initialize fresh per-request mappings; shallow context inheritance must not share mutable request state accidentally. |
| Named connections | `runtime._ThreadState` contains the current thread's connections and write state. | Replace the ownership mechanism, not the logical connection-name contract. Define which task owns each connection; never treat ContextVar as a concurrency lock. |
| Internal connection state | Database checks ownership and execution/commit flags in plain `_ConnectionState` dictionaries; no Session entity remains (report 28). | Replace the isolated ownership check with task ownership; thread identity is insufficient for async tasks on one thread. Keep fresh dictionaries per context and exclusive physical connection ownership. |
| Driver operations | Connect, execute, commit, rollback and close are synchronous. | Need awaited driver operations and async orchestration. Preserve compilation/driver boundaries; changing only the driver is insufficient. |
| Table hooks and deferred callbacks | Ordinary Python calls may perform synchronous DB operations. | Explicitly define the future async callback contract and ordering. Do not invent automatic coroutine detection or change failure propagation now. |
| Application entry point | Application-owned `db` property initializes request context; connections open lazily during execution. | Keep property lookup/context initialization free of network I/O. Async connection acquisition belongs in awaited execution; request cleanup belongs to the request owner. |
| Cleanup and failure | Explicit completion, original-error preservation, thread-local connection cleanup. | Async cleanup must account for cancellation and interrupted commit/rollback/close. Preserve the distinction between committed, rolled back and unknown outcomes; define cancellation handling when implementing async. |
| SQLite | Standard synchronous sqlite3; BEGIN IMMEDIATE may wait even for reads. | Direct calls would block an event loop. Choose and verify an async driver or controlled worker strategy separately, preserving connection ownership and documented locking limits. |
| Result API | Materialized results, synchronous terminals including fetch and immediate record reads. | I/O terminals need explicit async counterparts; this cannot preserve every synchronous call signature unchanged. Do not move their I/O into otherwise passive attributes. |

`SqlEnvironment` already uses ContextVar for its standalone snapshot-based
contract. That does not make `ApplicationEnvironment`, the live connection
registry or drivers async-safe. ContextVar copies bindings, not the underlying
mutable dictionaries or physical connections.

No reviewed choice here proves that async is impossible. The current runtime
requires deliberate changes; full migration cost and API design are not yet
certified. Any newly identified blocking decision must be added to this record.

## Future acceptance boundaries

When async implementation is undertaken, verify concurrent requests on one
thread, child-task context inheritance, exclusive connection ownership, nested
context restoration, cancellation during execution/completion, and cleanup
without leaking context, callbacks or transactions to the next request.
The synchronous tests remain the behavioral baseline where contracts are shared.
