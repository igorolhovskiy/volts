# volts-run — Run a VOLTS scenario and explain the results

Execute one or more VOLTS scenarios, then parse and explain the outcome in plain language.

**Input:** $ARGUMENTS
(Scenario name, tag filter, or empty to run all)

Examples:
- `003-register-wait-for-call-1` — run one scenario by name (with or without `.xml`)
- `scenarios/003-register-wait-for-call-1.xml` — same, with path prefix
- `tag=smoke` — run all scenarios tagged "smoke"
- `tag=smoke,regression` — run scenarios tagged smoke OR regression
- *(empty)* — run all scenarios

---

## Steps

### 1. Resolve the run target

Parse `$ARGUMENTS`:
- If empty → target is `` (run all)
- If starts with `tag=` → pass as-is
- If it looks like a filename (contains `-` or `.xml`) → use as scenario name, strip `scenarios/` prefix if present, strip `.xml` if present

### 2. Execute the run

From the project root, run:

```bash
./run.sh <target> -r json
```

If `$ARGUMENTS` is empty, run:
```bash
./run.sh -r json
```

Set a reasonable timeout. Most individual scenarios complete within 60 seconds; a full suite may take several minutes.

### 3. Parse the results

Each scenario produces a top-level JSON summary line followed by per-action detail lines in `tmp/output/<scenario>.jsonl`.

Top-level fields:
- `scenario` — scenario filename (no `.xml`)
- `voip_patrol` — `PASS` / `FAIL` / `N/A`
- `sipp` — `PASS` / `FAIL` / `N/A`
- `database` — `PASS` / `FAIL` / `N/A`
- `media` — `PASS` / `FAIL` / `N/A`
- `status` — overall: `PASS` only when all non-`N/A` components pass
- `text` — short human-readable result

Per-action fields:
- `label` — action label from the scenario XML
- `result` — `PASS` / `FAIL`
- `text` — detail message (e.g. "Main test passed", "Call canceled", error description)

### 4. Report the results

Print a clear summary in this structure:

```
## Results

✓ PASS  003-register-wait-for-call-1
✗ FAIL  007-delayed-call-forward

--- Failures ---

### 007-delayed-call-forward
  ✗ FAIL  voip_patrol
    - "Receive call on 88881 — no answer": FAIL — <text from result>
    - "Receive forwarded call on 88882": FAIL — <text from result>

  Likely cause: <your diagnosis>
  Suggested next step: <one concrete action>
```

**Diagnosis guidance:**

| Symptom | Likely cause |
|---------|-------------|
| Register FAIL with 401/403/407 | Wrong credentials, account not provisioned, or realm mismatch |
| Register FAIL with 408 | Domain unreachable or wrong transport |
| Call FAIL — expected 200 but got 486 | Callee busy or reject rule active |
| Call FAIL — expected 200 but got 404 | Callee not registered or wrong URI |
| Call FAIL — expected 200 but got 408 | Callee not answering within `max_ring_duration` |
| Accept FAIL — "no call received" | PBX didn't route the call to this account |
| Accept FAIL with `fail_on_accept` | A call arrived when none was expected |
| Cancel not received | No-answer forward not configured on PBX |
| media FAIL | Audio level or length outside expected range; possible codec mismatch or silent call |

### 5. If all pass

Print a single line:
```
All scenarios passed. ✓
```
