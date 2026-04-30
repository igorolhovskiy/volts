# volts-new — Create a new VOLTS scenario

Create a new VOLTS functional test scenario from a natural language description.

**Input:** $ARGUMENTS
(Natural language description of what the scenario should test.
Example: "register 88881 and receive a call from 88882 with DTMF 1234, verify it lands on 88881")

---

## Steps

### 1. Load reference material

Read both files before writing anything:

- `ai/VOLTS_AI.md` — complete format reference (actions, attributes, ordering rules, Jinja2 variables)
- `scenarios/config.yaml` — available accounts, domain, transport, srtp, play_file values

Only use accounts and Jinja2 variables that exist in `config.yaml`. Never invent account numbers.

### 2. Choose a filename

List `scenarios/` and find the highest numeric prefix currently in use. Use the next available three-digit number.
Format: `NNN-short-description.xml` (lowercase, hyphens, no spaces).
Example: if `248-call-external-reinvite.xml` is the highest, the new file is `249-<description>.xml`.

### 3. Identify which section types are needed

| Need | Section |
|------|---------|
| SIP register / call / accept | `voip_patrol` |
| Inline SIPp scenario | `sipp` |
| Database seed/cleanup | `database` |
| WAV file quality check | `media_check` |

If the description mentions database operations, include a `database` section. If it mentions media/audio quality, include a `media_check` section. Otherwise use only `voip_patrol`.

### 4. Apply the mandatory ordering rules

Inside a `voip_patrol` section, actions must appear in this order:

1. `codec` (disable all, then re-enable what's needed) — always first when audio is involved
2. `register` — for every account that will receive calls
3. `<action type="wait" complete="true" ms="2000"/>` — after registers, before accept/call
4. `accept` — **must appear before its corresponding `call`**
5. `call`
6. `<action type="wait" complete="true" ms="…"/>` — always last; use at least 2× the expected call duration

### 5. Use helpers where they match

Check `scenarios/helpers/` for available partials:

- `codecs-default.j2` — disables all codecs and enables opus + pcma (use instead of manual codec actions when these codecs are sufficient)
- `register-200.j2` — standard register expecting 200; requires `{% with endpoint = NNNNN %}` wrapper

Include them with:
```xml
{% include "helpers/codecs-default.j2" %}

{% with endpoint = 88881 %}
{% include "helpers/register-200.j2" %}
{% endwith %}
```

### 6. Jinja2 variables

Always use config variables — never hardcode domains, passwords, or transport:

| Use this | For |
|----------|-----|
| `{{ c.domain }}` | SIP domain |
| `{{ c.transport }}` | default transport |
| `{{ c.srtp }}` | default SRTP mode |
| `{{ c.play_file }}` | reference audio file |
| `{{ a.NNNNN.username }}` | account SIP username |
| `{{ a.NNNNN.label }}` | same as username (alias) |
| `{{ a.NNNNN.password }}` | account password |
| `{{ a.NNNNN.transport }}` | per-account transport (inherits from global) |
| `{{ a.NNNNN.srtp }}` | per-account SRTP (inherits from global) |
| `{{ a.NNNNN.domain }}` | per-account domain (inherits from global) |
| `{{ scenario_name }}` | filename without `.xml` — use for `record` attributes |

### 7. Common scenario patterns

**Call that should be answered:**
```xml
<action type="accept" … code="200" reason="OK" hangup="10"/>
<action type="call"   … expected_cause_code="200" hangup="10"/>
```

**Call that should be rejected (busy/blocked):**
```xml
<action type="accept" … fail_on_accept="true"/>   <!-- PASS only if NO call arrives -->
<action type="call"   … expected_cause_code="486"/>
```

**No-answer forward (ring then cancel, then forwarded leg answered):**
```xml
<action type="accept" label="Ring 88881 — no answer"
    match_account="88881" call_count="1"
    ring_duration="30" cancel="force" …/>
<action type="accept" label="Forwarded to 88882"
    match_account="88882" call_count="1"
    code="200" reason="OK" hangup="10" …/>
<action type="call" … max_ring_duration="60"/>
```

**SIP header assertion on accepted call:**
```xml
<action type="accept" …>
    <check-header name="From" regex="^.*sip:{{ a.90001.label }}@{{ c.domain }}.*$"/>
</action>
```

**DTMF — append to callee field:**
```xml
callee="{{ a.88881.label }},123,A3@{{ c.domain }}"   <!-- sends DTMF 1 2 3 A 3 after answer -->
```

**Media recording + quality check:**
```xml
<!-- in voip_patrol -->
record="{{ scenario_name }}.wav"

<!-- in media_check -->
<action type="sox_st"
    file="{{ scenario_name }}.wav"
    length="9-11"
    sox_filter="maximum amplitude -ge 0.9; minimum amplitude -le -0.5"
/>
```

### 8. Write the file

Write the completed XML to `scenarios/NNN-description.xml`.

Then print a short summary (3–5 lines) explaining:
- What the scenario tests
- Which accounts are involved and their roles
- The expected SIP flow (e.g. "90001 calls 88881 → 88881 rings 30s → CANCEL → forwarded to 88882 → answered")
- The filename chosen and why
