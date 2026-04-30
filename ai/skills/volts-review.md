# volts-review — Review a VOLTS scenario for correctness

Systematically review one or more VOLTS scenario files and report every problem with an actionable fix.

**Input:** $ARGUMENTS
(Scenario filename, glob, or empty to review all scenarios)

Examples:
- `007-delayed-call-forward.xml` — review one file
- `scenarios/007-delayed-call-forward.xml` — same, with path prefix
- *(empty)* — review every file in `scenarios/` (skip `config.yaml.template`)

---

## Steps

### 1. Load reference material

Read these files first:

- `ai/VOLTS_AI.md` — authoritative format reference
- `scenarios/config.yaml` — source of truth for valid accounts, domain, transport, srtp, databases

### 2. Resolve files to review

- If `$ARGUMENTS` is empty: list all `scenarios/*.xml` files
- Otherwise: resolve the given path(s)

Read each target file in full.

### 3. Run all checks

Apply every check below to each file. Collect findings — do not stop at the first issue.

---

#### A. Structural checks

- [ ] Root element is `<config>` (not `<actions>` at top level unless it's the voip_patrol shorthand)
- [ ] Every `<section>` has a valid `type`: `voip_patrol`, `sipp`, `database`, `media_check`
- [ ] No unknown XML elements or attributes (typos like `<acton>`, `type="regiser"`)
- [ ] Jinja2 syntax is valid — balanced `{{`/`}}` and `{%`/`%}`, no unclosed blocks

#### B. Account reference checks

For every `{{ a.NNNNN.* }}` reference:
- [ ] Account `NNNNN` exists as a key under `accounts:` in `config.yaml`
- [ ] No hardcoded usernames, passwords, or domains that should use `{{ a.NNNNN.* }}` or `{{ c.* }}`

For every `database="DBNAME"` attribute:
- [ ] `DBNAME` exists as a key under `databases:` in `config.yaml`

#### C. voip_patrol ordering checks

Within each `voip_patrol` section, verify this order is respected:

1. `codec` actions come before any `register`, `call`, or `accept`
2. `register` actions come before `accept` and `call`
3. A `<action type="wait" complete="true" ms="…"/>` appears after all registers and before any `accept`/`call` (the 2-second settle wait)
4. Every `accept` action appears **before** its corresponding `call` in the XML source
5. The final action is `<action type="wait" complete="true" ms="…"/>` — not a `call` or `accept`

#### D. accept / call pairing checks

- [ ] Every `accept` with `match_account="X"` has a corresponding `call` that targets account `X` (or `match_account="default"` is used intentionally)
- [ ] `call_count` on `accept` matches the number of `call` actions targeting that account
- [ ] If `cancel="force"` is set, there is a second `accept` for the forwarded destination
- [ ] If `fail_on_accept="true"` is set, confirm there is **no** corresponding call expected to succeed on that account (it's a "must not receive" assertion)
- [ ] `match_account` value matches the `account` attribute used in the corresponding `register`

#### E. Timing and duration checks

- [ ] `hangup` on `call` ≤ `max_duration` on the same call
- [ ] Final `wait complete ms` value is at least 2× the longest `max_duration` or `ring_duration` in the scenario
- [ ] If `ring_duration` is set on an `accept`, `max_ring_duration` on the corresponding `call` is larger than `ring_duration` (so the call doesn't give up before the ring times out)

#### F. Transport and SRTP consistency

- [ ] If an `accept` uses `srtp="sdes,force"`, the corresponding `call` also uses a compatible SRTP mode (not empty)
- [ ] `transport="wss"` is not combined with a `proxy` attribute on the same `call` action (WSS uses the OpenSIPS proxy internally)
- [ ] If `transport="wss"` is used, a `<action type="turn" …/>` + `<action type="wait" ms="5000"/>` appears before the call

#### G. Media check consistency

- [ ] Every `record="<file>"` in a `voip_patrol` action has a matching `file="<file>"` in the `media_check` section (or the recording is intentionally unanalyzed — note this)
- [ ] `{{ scenario_name }}.wav` naming is used consistently (not a hardcoded filename)
- [ ] `fpcalc` actions have a non-empty `fingerprint` attribute
- [ ] `sox_filter` expressions use bash-style operators (`-ge`, `-le`, `-eq`, `-ne`, `-lt`, `-gt`), not `<`/`>`/`=`

#### H. Database section checks

- [ ] Every `type="insert"` with `cleanup_after_test="true"` does **not** need an explicit `stage="post"` delete (auto-generated)
- [ ] Every `type="delete"` with `cleanup_after_test="true"` will be re-inserted after the test — confirm this is intentional
- [ ] `type="replace"` does **not** have `cleanup_after_test="true"` (replace does not support auto-cleanup)
- [ ] `stage` is either `pre` or `post`

#### I. Style / DRY checks

- [ ] If the same `register` block appears in 3+ scenarios, suggest extracting it to a helper in `scenarios/helpers/`
- [ ] Existing helpers are used where they match (e.g. `register-200.j2`, `codecs-default.j2`) instead of duplicating the XML inline

---

### 4. Report findings

For each file, print a section like:

```
## 007-delayed-call-forward.xml

✓ No issues found.
```

or:

```
## 007-delayed-call-forward.xml

### [C4] accept appears after call — ordering violation
Line ~34: `accept` for account 88882 appears after the `call` action.
`accept` must be declared before the corresponding `call` because it is set up asynchronously.
**Fix:** move the `accept` block above the `call` block.

### [E3] final wait may be too short
`wait complete ms="15000"` but `max_ring_duration="30"` on the call.
Final wait should be at least 60 000 ms to allow the full ring + call duration to complete.
**Fix:** change to `ms="60000"`.
```

Use the check letter+number as a short ID (e.g. `[C4]`, `[E3]`) so fixes are easy to reference.

End with a one-line summary:
```
3 issues found in 1 file. 0 files clean.
```
or:
```
All 5 files reviewed. No issues found.
```
