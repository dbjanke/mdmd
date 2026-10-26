## Agent Guidance

This repo favors modular design with strict boundaries.

Keep core logic separate from IO, framework glue, and external mechanisms.
Implementation details should remain behind stable interfaces.

**Simplicity means no entanglement.** A simple system is one where components
are not braided together — where each module, function, and concept can be
understood, tested, and changed without pulling on something else. Simplicity
is not about counting. Splitting a tangled module into three focused ones is
the right outcome, even when it produces more files. Prefer more things with
no twists over fewer things tied in a knot.

Operational rule: abstract at module boundaries; stay concrete and explicit
within modules.

---

## Workflow (Default Operating Mode)

Make the smallest change that solves the problem.

Do not refactor unrelated code. If issues are noticed, call them out but do
not fix them unless asked.

Prefer existing patterns over introducing new ones.

Keep diffs reviewable. Avoid drive-by renames, formatting churn, or
reorganization.

When uncertain about the right approach and the situation does not clearly
trigger the "ask before" list below, surface it anyway. A short question is
cheaper than a wrong assumption.

Ask before changes that:

* affect user-visible behavior in a non-trivial way
* introduce new dependencies
* add architectural layers or generalized frameworks
* expand scope beyond the requested fix or feature
* change configuration behavior in a way that could surprise callers

**When stuck:** after two failed attempts at the same problem, stop. Do not
try another variation. Instead, surface what is actually known: what the
system is doing, what it should be doing, and where the gap is. Add tests if
needed to confirm actual behavior before forming a new hypothesis. The next
action is to reason out loud and align with the user, not to attempt another
fix.

---

## Living Documents

Keep the following files accurate and current as the project evolves.

**README.md** covers user-facing information: what the project is, how to
install it, and how to use it. Create it if it does not exist. Update it
whenever behavior, setup steps, or interfaces change in a user-visible way.

**DESIGN.md** covers implementation intent: architecture decisions, key
tradeoffs, and how the system is structured. Update it when structural or
architectural decisions change, not for every small fix.

---

## Architecture Boundaries

Boundaries are intentional. Do not leak concepts across them.

* **Core logic**: policy, orchestration, validation, limits, and business rules.

  * Keep functions small, explicit, and testable.
  * Prefer composition over inheritance.
  * Core logic must not depend directly on framework or vendor-specific details.

* **External integrations**: API clients, filesystem access, config loading,
  and other IO.

  * Keep integration details local.
  * Expose stable, narrow interfaces to the rest of the codebase.
  * Do not let transport or library choices shape core logic.

* **Configuration**: explicit loading and validation.

  * Fail fast on missing or invalid configuration.
  * Do not hide behavior behind implicit defaults.
  * Keep configuration separate from logic.
  * When config drives data column selection, list the columns explicitly in the config. Do not infer which columns to use from their presence in the data.

* **Environment-level parameters** belong in `.env`, loaded via dotenv (or the
  platform equivalent). This includes ports, hostnames, API keys, database
  connection details, and any value that changes between environments or must
  be kept out of source control.

  * Provide a `.env.example` that documents every required variable with a
    placeholder or description. Keep it current.
  * Never hardcode environment-level values, even as fallbacks. If a required
    variable is absent, fail fast with a clear error.
  * `.env` is never committed. `.env.example` always is.

Introduce abstractions only when they reduce what a caller must understand.

Avoid generalization that increases conceptual surface area without a
corresponding reduction in coupling.

---

## Project Tenets (Trade-off Overrides)

1. **Optimize for operational calm.**
   Prefer designs that are predictable, hard to misuse, and low-maintenance.

2. **Focus on clarity.**
   Prioritize depth, correctness, and readability over cleverness or novelty.

3. **Shape before scale.**
   Choose the simplest architecture that preserves intent. Resist premature
   infrastructure.

---

## Principles

### Simplicity & Structure

* Each module, function, and concept should have one clear role. If you need
  "and" to describe what something does, it is doing too much.
* A focused component in its own file is preferable to merging concerns to
  reduce file count. More things, clearly separated, is better than fewer
  things entangled.
* Abstract at boundaries; remain explicit within modules.
* Separate policy from mechanism.
* Avoid universal or framework-shaped machinery unless the domain clearly
  demands it.
* Prefer composition and focused, testable units.

### Constants & Configuration

* Do not mix values with logic. Separate data from behavior.
* Behavior constants such as limits, retries, timeouts, thresholds, and flags
  belong in config or named constants.
* Avoid magic numbers and unexplained string literals.
* Clarity of meaning outweighs convenience of inlining.

### Explicitness & Correctness

* Prefer explicit logic, limits, and error handling over implicit behavior.
* Fail fast when assumptions or required configuration are unmet.
* Prefer clear, actionable errors.
* Resolve warnings promptly. If suppression is necessary, document why.

### Quality & Change Management

* Tests are expected unless the change is purely mechanical.
* Tests should define behavior at boundaries and constrain correctness, not
  just execute the happy path. A test that would not catch a logic inversion
  in the function it covers is not providing meaningful coverage.
* After large changes or heavy debugging, reassess structure: remove kludges,
  simplify, and realign to the real use-case before shipping.

### Monitoring & Observability

Every feature that touches state, external systems, or user-visible behavior
should be observable by default — not instrumented as an afterthought.

When adding a new feature, ask:

* What does healthy behavior look like, and can we measure it?
* What failure modes exist, and will they surface before users report them?
* What should be in a log entry when something goes wrong?

Concrete expectations:

* **Structured logging**: use structured log output (key-value or JSON). Avoid
  freeform strings that cannot be queried or aggregated.
* **Error tracking**: unhandled exceptions and unexpected states should route
  to an error tracker, not just logs. Include enough context to reproduce —
  request shape, system state, relevant IDs — never raw user content.
* **Key metrics**: track what matters for operational health — request counts,
  error rates, latency, queue depth, external call outcomes. If a metric does
  not inform a decision or an alert, it is probably noise.
* **Alerting**: critical paths should have alerts. An on-call engineer should
  learn about a production failure from the system, not from a user.
* **Avoid over-instrumentation**: more signals is not better. Every metric and
  log line has a maintenance cost. Instrument what you will actually look at.

### Operability, Security, Privacy

* Keep diagnostics straightforward and useful.
* Follow least-privilege and defense-in-depth principles.
* Prefer well-supported, widely adopted dependencies.

**Privacy defaults are strict.** User content is not available to be logged,
traced, stored in error reports, or surfaced in analytics without a deliberate,
justified decision to do so. The default answer is no.

* Logs and error reports may reference IDs, shapes, and counts — not content.
* Aggregated, anonymized metrics are preferred over any form of raw content
  capture.
* When in doubt, drop the data. The cost of not having a log line is lower
  than the cost of a content exposure.

### UX / Interaction

* User-facing behavior should be minimal, clear, and unsurprising.
* Reinforce user agency and reduce cognitive load.
* Prefer familiar patterns when they improve clarity.
* Avoid unnecessary verbosity, decoration, or friction.
* Visual changes require functional justification. If a change does not improve
  clarity, usability, or correctness, it does not belong in a diff.