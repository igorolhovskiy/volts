# VOLTS AI Reference

**Voip Open Linear Tester Suite** — functional testing framework for VoIP/SIP PBX systems.
Run call scenarios, seed databases, check media quality, inspect SIP headers. All driven by XML scenario files with Jinja2 templating.

---

## Quick orientation

```
volts/
├── run.sh                  # main entry point — runs all scenarios or one
├── build.sh                # builds Docker images (do this once)
├── scenarios/
│   ├── config.yaml         # global config + account credentials
│   ├── helpers/            # reusable Jinja2 includes (.j2)
│   └── NN-name.xml         # test scenarios, run alphabetically
└── tmp/output/             # results land here after a run
```

Tests run **sequentially** in filename alphabetical order. Prefix filenames with numbers to control order (`01-register.xml`, `02-call.xml`, …).

---

## Running tests

```bash
./run.sh                          # run all scenarios
./run.sh 05-forward.xml           # run one scenario
./run.sh scenarios/05-forward.xml # same, with path prefix
./run.sh tag=smoke                # run all scenarios tagged "smoke"
./run.sh tag=smoke,regression     # run scenarios tagged smoke OR regression
```

**Useful flags:**

| Flag | Description |
|------|-------------|
| `-r table` / `-r json` | Report format (`table`, `table_full`, `json`, `json_full`) |
| `-l 0..3` | Log verbosity (0 = silent, 3 = verbose) |
| `-t N` | Max seconds a single scenario may run (default 120) |

**Special commands:**

```bash
./run.sh sngrep    # live SIP capture (run in a second terminal during tests)
./run.sh report-only  # reprint last results without re-running
./run.sh dbclean   # run only the database "post" cleanup stages
```

---

## config.yaml — global settings and accounts

Loaded by every scenario via Jinja2. Structure:

```yaml
global:
  domain:           'sip.example.com'     # primary SIP domain
  domain_wss:       'sip.example.com:8089' # WSS domain (for WebSocket tests)
  transport:        'tls'                  # default transport: udp/tcp/tls/wss
  srtp:             'sdes,force'           # SRTP mode: sdes,force / dtls,force / ''
  dtls:             'dtls,force'           # DTLS variant (used for WSS/DTLS tests)
  play_file:        '/voice_ref_files/8000_2m30.wav'
  play_file_2:      '/voice_ref_files/test01_20s.wav'
  stun_address:     'stun.example.com:3478'
  asterisk_context: 'default'

databases:
  'mydb':           # key used in <action database="mydb">
    type:     'mysql'    # mysql or pgsql
    user:     'dbuser'
    password: 'dbpass'
    base:     'dbname'
    host:     'db.local'

accounts:
  '88881':
    username:       '88881'       # SIP username (used in AOR)
    auth_username:  '88881-auth'  # WWW-Authenticate username (defaults to username)
    password:       'secret'
    ha1:            'md5hash'     # optional, used instead of password for HA1 auth
    # any extra fields are accessible as a.88881.<field>
```

### Jinja2 variables in scenarios

| Variable | Resolves to |
|----------|-------------|
| `{{ c.domain }}` or `{{ g.domain }}` | `global.domain` |
| `{{ c.<key> }}` | any key under `global` |
| `{{ a.88881.username }}` | account field |
| `{{ a.88881.label }}` | same as `username` (alias) |
| `{{ a.88881.domain }}` | falls back to `c.domain` unless overridden in account |
| `{{ a.88881.transport }}` | falls back to `c.transport` |
| `{{ a.88881.srtp }}` | falls back to `c.srtp` |
| `{{ scenario_name }}` | filename without `.xml` (e.g. `05-forward`) |
| `{{ env.MY_VAR }}` | environment variable (empty string if unset) |
| `{{ env.MY_VAR \| default('fallback') }}` | env var with fallback |
| `{% now 'local' %}` | current local datetime |
| `{% now 'utc', '%H:%M' %}` | UTC time formatted |
| `{% now 'local' + 'days=1', '%w' %}` | relative time offset |
| `{% include "helpers/register-200.j2" %}` | include a helper partial |

> **All global keys are inherited by accounts.** An account only needs to define keys that differ from `global`.

---

## Scenario XML format

Every scenario is one XML file. Root element is `<config>`. It contains one or more `<section>` elements (or `<actions>` directly for voip_patrol shorthand).

```xml
<config tag="optional,comma,separated,tags">

    <section type="database">…</section>   <!-- optional -->
    <section type="voip_patrol">…</section> <!-- or sipp -->
    <section type="media_check">…</section> <!-- optional -->

</config>
```

Tags are used for selective test runs (`./run.sh tag=smoke`). A scenario with no tag runs always.

---

## Section: voip_patrol

Tests SIP behavior (REGISTER, CALL, ACCEPT, codec negotiation, DTMF, hold/unhold, headers).

```xml
<section type="voip_patrol">
    <actions>
        <!-- actions go here -->
    </actions>
</section>
```

Shorthand (no `<section>` wrapper, valid when there is only a voip_patrol section):

```xml
<config>
    <actions>
        <!-- voip_patrol actions -->
    </actions>
</config>
```

### action: codec

Always put codec actions **before** register/call. Disable all first, then re-enable what you want.

```xml
<action type="codec" disable="all"/>
<action type="codec" enable="pcma" priority="250"/>
<action type="codec" enable="pcmu" priority="249"/>
<action type="codec" enable="opus" priority="248"/>
```

### action: register

Registers a SIP account. Creates an account object (referenced by `match_account` in `accept`).

```xml
<action type="register"
    label="Register 88881"           <!-- display label in results -->
    transport="tls"                  <!-- udp / tcp / tls / wss -->
    account="88881"                  <!-- account name, referenced by accept/match_account -->
    username="88881"                 <!-- SIP username (AOR part) -->
    auth_username="88881"            <!-- WWW-Authenticate username -->
    password="secret"
    registrar="sip.example.com"      <!-- registrar hostname/IP -->
    realm="sip.example.com"
    expected_cause_code="200"        <!-- 200 = success, 401/403/407 = auth failure -->
    srtp="sdes,force"                <!-- SRTP: sdes,force / dtls,force / '' -->
    require_100rel="force"           <!-- optional: force PRACK (100rel) -->
/>
```

### action: accept

Listens for an incoming call. **Must be placed before the corresponding `call` action.**

```xml
<action type="accept"
    label="Receive call on 88881"
    call_count="1"                   <!-- how many calls to expect -->
    match_account="88881"            <!-- account name from a prior register; "default" = any -->
    code="200" reason="OK"           <!-- SIP response to send (200 = answer) -->
    hangup="10"                      <!-- seconds before hanging up after answer -->
    ring_duration="30"               <!-- optional: ring for this many seconds before answering -->
    cancel="force"                   <!-- optional: expect CANCEL (no-answer forward scenarios) -->
    fail_on_accept="true"            <!-- optional: FAIL the test if a call IS received -->
    transport="tls"
    srtp="sdes,force"
    play="/voice_ref_files/8000_2m30.wav"   <!-- optional: play file during call -->
    record="scenarioname.wav"        <!-- optional: record received audio to file -->
    rtp_stats="true"                 <!-- optional: collect RTP stats -->
>
    <!-- optional SIP header assertions -->
    <check-header name="From" regex="^.*sip:90001@example\.com.*$"/>
    <check-header name="P-Asserted-Identity" regex="^.*\+1234.*$"/>
</action>
```

### action: call

Makes an outgoing SIP call.

```xml
<action type="call"
    label="Call 90001 -> 88881"
    transport="tls"                  <!-- udp / tcp / tls / wss -->
    expected_cause_code="200"        <!-- 200 = answered, 486 = busy, 404 = not found, etc. -->
    caller="90001@sip.example.com"   <!-- From display (caller@domain) -->
    callee="88881@sip.example.com"   <!-- Request-URI user/domain -->
    from="sip:90001@sip.example.com" <!-- From header URI -->
    to_uri="88881@sip.example.com"   <!-- To header URI -->
    max_duration="20"                <!-- max call duration in seconds -->
    hangup="10"                      <!-- hang up N seconds after answer -->
    max_ring_duration="15"           <!-- give up ringing after N seconds -->
    auth_username="90001"
    password="secret"
    realm="sip.example.com"
    srtp="sdes,force"
    play="/voice_ref_files/8000_2m30.wav"   <!-- optional: play file during call -->
    record="scenarioname.wav"        <!-- optional: record sent/received audio -->
    rtp_stats="true"                 <!-- optional: collect RTP/RTCP stats -->
    proxy="proxy.example.com"        <!-- optional: outbound proxy (cannot use with wss) -->
/>
```

> **DTMF:** append DTMF digits to the callee field: `callee="88881,123,A3@domain"` — the part after the first comma is the DTMF sequence, A–D are DTMF A–D, digits 0–9 and `*#` are standard.

### action: wait

Pause execution. Required at the end of most scenarios to let async events settle.

```xml
<action type="wait" ms="2000"/>                      <!-- wait N ms -->
<action type="wait" complete="true" ms="30000"/>     <!-- wait until all actions done OR timeout -->
```

### action: hold / unhold

Put the current call on hold and resume it (sends re-INVITE with `a=sendonly`/`a=sendrecv`).

```xml
<action type="hold"   label="Put on hold"   caller="88882"/>
<action type="wait"   ms="10000"/>
<action type="unhold" label="Take off hold" caller="88882"/>
```

`caller` references the `account` name used in the earlier `register` action.

### action: turn

Enable/disable STUN/TURN for ICE (required for WSS/WebRTC scenarios).

```xml
<action type="turn" enabled="true" server="stun.example.com:3478" stun_only="true"/>
<action type="wait" ms="5000"/>   <!-- wait for ICE gathering -->
```

---

## Section: database

Seeds or cleans the database before/after the VoIP test. Uses `stage="pre"` (runs before voip_patrol) and `stage="post"` (runs after). `cleanup_after_test="true"` auto-generates the `post` DELETE so you don't have to write it explicitly.

```xml
<section type="database">
    <actions>
        <action database="mydb" stage="pre">
            <table name="subscriber" type="insert" cleanup_after_test="true">
                <field name="username" value="{{ a.88881.username }}"/>
                <field name="domain"   value="{{ c.domain }}"/>
                <field name="password" value="{{ a.88881.password }}"/>
            </table>
        </action>
    </actions>
</section>
```

### Table attributes

| Attribute | Values | Description |
|-----------|--------|-------------|
| `name` | string | Database table name |
| `type` | `insert` `replace` `delete` | SQL operation |
| `cleanup_after_test` | `true` | Auto-DELETE matching rows in `post` stage (only for `insert`) |
| `continue_on_error` | `true` | Ignore errors and keep going |

> **`replace`** = `REPLACE INTO` (MySQL upsert). Does NOT trigger auto-cleanup.
> **`delete`** with `cleanup_after_test="true"` will re-INSERT deleted rows after the test (restore).

---

## Section: sipp

Embeds a SIPp scenario inline. The scenario XML content goes inside `<scenario>`. Jinja2 templating works inside `CDATA` blocks.

```xml
<section type="sipp">
    <actions>
        <action
            transport="tls"              <!-- udp / tcp / tls -->
            target="sip.example.com"     <!-- SIPp target host -->
            max_calls="1"                <!-- -m option (default: 1) -->
            call_rate="10"               <!-- -r option (default: 10) -->
            max_concurrent_calls="10"    <!-- -l option (default: 10) -->
            socket_mode="single"         <!-- single / multi -->
            total_timeout="600"          <!-- seconds before force-stop -->
        >
            <scenario name="OPTIONS health check">
                <send>
                    <![CDATA[
OPTIONS sip:health@{{ c.domain }} SIP/2.0
Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
Max-Forwards: 70
To: <sip:health@{{ c.domain }}>
From: sipp <sip:health@[local_ip]:[local_port]>;tag=[call_number]
Call-ID: [call_id]
CSeq: 1 OPTIONS
Contact: <sip:health@[local_ip]:[local_port]>
Content-Length: 0
                    ]]>
                </send>
                <recv response="200" timeout="200"/>
            </scenario>
        </action>
    </actions>
</section>
```

SIPp keywords: `[local_ip]`, `[local_port]`, `[remote_ip]`, `[remote_port]`, `[call_id]`, `[branch]`, `[call_number]`, `[transport]`, `[authentication ...]`, `[len]`.

---

## Section: media_check

Analyzes WAV files recorded during the call. The `file` attribute must match the `record` attribute of a voip_patrol `call` or `accept` action.

```xml
<section type="media_check">
    <actions>
        <action type="sox"    …/>   <!-- SoX stats check -->
        <action type="sox_st" …/>   <!-- SoX with silence trimming first -->
        <action type="fpcalc" …/>   <!-- Chromaprint fingerprint similarity -->
    </actions>
</section>
```

### Common attributes (all types)

| Attribute | Default | Description |
|-----------|---------|-------------|
| `file` | required | Path to WAV file (relative to `tmp/` output dir) |
| `length` | — | Expected duration: `"10"` exact, `"9-11"` range (seconds) |
| `delete_after` | `keep_failed` | `yes` / `no` / `keep_failed` |
| `print_debug` | `no` | Print raw SoX/fpcalc output to console |

### type="sox" / type="sox_st"

Checks parameters from `sox <file> -n stats`. `sox_st` trims silence before checking.

```xml
<action type="sox"
    file="{{ scenario_name }}.wav"
    length="10-11"
    sox_filter="maximum amplitude -ge 0.9; minimum amplitude -le -0.5; rms lev db -ge -35"
/>
```

`sox_filter` is a semicolon-separated list of expressions: `<parameter name> <operator> <value>`.

Operators are bash-style: `-eq` `-ne` `-lt` `-le` `-gt` `-ge`.

Common SoX parameters (all lowercase):

| Parameter | Type | Example |
|-----------|------|---------|
| `length s` | float | `length s -ge 10` |
| `maximum amplitude` | float | `maximum amplitude -ge 0.9` |
| `minimum amplitude` | float | `minimum amplitude -le -0.5` |
| `rms lev db` | float | `rms lev db -ge -30` |
| `pk lev db` | float | `pk lev db -le -5` |
| `dc offset` | float | |
| `bit-depth` | string | `bit-depth -eq 16/16` |
| `crest factor` | float | |

> `length` shorthand: `length="10-11"` is equivalent to `sox_filter="length s -ge 10; length s -le 11"`.

### type="fpcalc"

Checks acoustic fingerprint similarity using Chromaprint. Best with 10–30 s of audio.

```xml
<action type="fpcalc"
    file="{{ scenario_name }}.wav"
    fingerprint="3089777192, 3089826344, 3089901096, …"   <!-- raw fingerprint from fpcalc -raw -->
    likeness="0.85"        <!-- minimum similarity 0..1 (default: 0.9) -->
    length="9.5-10.5"      <!-- optional duration check -->
    max_offset="4"         <!-- optional: allow ±N * 0.5s offset (default: 0) -->
/>
```

Likeness guide:

| Score | Meaning |
|-------|---------|
| 0.95 – 1.00 | Near identical |
| 0.85 – 0.95 | Same content, noticeable degradation |
| 0.70 – 0.85 | Possibly related, uncertain |
| < 0.70 | Likely different content |

To get a fingerprint for a reference file:

```bash
docker run --rm -v $(pwd)/tmp:/tmp volts_media fpcalc -raw /tmp/myfile.wav
```

---

## Helper templates (Jinja2 includes)

Reusable partials live in `scenarios/helpers/`. Include them with:

```xml
{% include "helpers/register-200.j2" %}
```

Pass variables with `{% with %}`:

```xml
{% with endpoint = 90002 %}
{% include "helpers/register-200.j2" %}
{% endwith %}
```

Inside the partial, `a[endpoint]` resolves to `a.90002`.

Existing helpers:

| File | What it does |
|------|-------------|
| `register-200.j2` | `register` action expecting 200, uses `endpoint` variable |
| `astdb-endpoint.j2` | INSERT into Asterisk `ps_endpoints` + `ps_aors`, uses `endpoint` variable |
| `sipproxydb-endpoint.j2` | INSERT into SIP proxy `subscriber` table, uses `endpoint` variable |

---

## Result format

Default output is a table printed to stdout. For machine-readable output use `-r json`:

```bash
./run.sh -r json
```

Each scenario produces a JSONL line in `tmp/output/<scenario>.jsonl`. The report container aggregates these.

### JSON result structure (per test action)

```json
{
  "scenario": "05-forward",
  "label": "Register 88881",
  "result": "PASS",
  "text": "Main test passed"
}
```

Top-level scenario result:

```json
{
  "scenario": "05-forward",
  "voip_patrol": "PASS",
  "sipp": "N/A",
  "database": "PASS",
  "media": "N/A",
  "status": "PASS",
  "text": "Scenario passed"
}
```

`status` is `PASS` only when all non-`N/A` components pass.

---

## Worked examples

### 1. Minimal register test

```xml
<config>
    <actions>
        <action type="register" label="Register {{ a.88881.username }}"
            transport="{{ a.88881.transport }}"
            account="{{ a.88881.username }}"
            username="{{ a.88881.label }}"
            auth_username="{{ a.88881.username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ c.domain }}"
            expected_cause_code="200"
        />
        <action type="wait" complete="true" ms="2000"/>
    </actions>
</config>
```

### 2. Register + make a call (expect answer)

```xml
<config>
    <actions>
        <action type="codec" disable="all"/>
        <action type="codec" enable="pcma" priority="250"/>
        <action type="codec" enable="pcmu" priority="249"/>
        <action type="register" label="Register {{ a.88881.username }}"
            transport="{{ a.88881.transport }}"
            account="{{ a.88881.username }}"
            username="{{ a.88881.label }}"
            auth_username="{{ a.88881.username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ c.domain }}"
            expected_cause_code="200"
            srtp="{{ a.88881.srtp }}"
        />
        <action type="wait" complete="true" ms="2000"/>
        <action type="accept" label="Receive call on {{ a.88881.username }}"
            call_count="1"
            match_account="{{ a.88881.username }}"
            hangup="10"
            code="200" reason="OK"
            transport="{{ a.88881.transport }}"
            srtp="{{ a.88881.srtp }}"
            play="{{ c.play_file }}"
        />
        <action type="call" label="Call {{ a.90001.label }} -> {{ a.88881.label }}"
            transport="{{ a.90001.transport }}"
            expected_cause_code="200"
            caller="{{ a.90001.label }}@{{ c.domain }}"
            callee="{{ a.88881.label }}@{{ c.domain }}"
            from="sip:{{ a.90001.label }}@{{ c.domain }}"
            to_uri="{{ a.88881.label }}@{{ c.domain }}"
            max_duration="20" hangup="10"
            auth_username="{{ a.90001.username }}"
            password="{{ a.90001.password }}"
            realm="{{ c.domain }}"
            rtp_stats="true"
            max_ring_duration="15"
            srtp="{{ a.90001.srtp }}"
            play="{{ c.play_file }}"
        />
        <action type="wait" complete="true" ms="30000"/>
    </actions>
</config>
```

### 3. Database seed + register (no-answer forward scenario)

```xml
<config>
    <section type="database">
        <actions>
            <action database="sippproxydb" stage="pre">
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain"   value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="voip_patrol">
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="register" label="Register {{ a.88881.username }}"
                transport="{{ a.88881.transport }}"
                account="{{ a.88881.username }}"
                username="{{ a.88881.label }}"
                auth_username="{{ a.88881.username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ c.domain }}"
                expected_cause_code="200"
                srtp="{{ a.88881.srtp }}"
            />
            <action type="register" label="Register {{ a.88882.username }}"
                transport="{{ a.88882.transport }}"
                account="{{ a.88882.username }}"
                username="{{ a.88882.label }}"
                auth_username="{{ a.88882.username }}"
                password="{{ a.88882.password }}"
                registrar="{{ c.domain }}"
                realm="{{ c.domain }}"
                expected_cause_code="200"
                srtp="{{ a.88882.srtp }}"
            />
            <action type="wait" complete="true" ms="2000"/>
            <!-- 88881 rings but doesn't answer → PBX forwards to 88882 -->
            <action type="accept" label="Receive call on {{ a.88881.username }} - no answer"
                call_count="1"
                match_account="{{ a.88881.username }}"
                ring_duration="30"
                cancel="force"
                transport="{{ a.88881.transport }}"
                srtp="{{ a.88881.srtp }}"
            />
            <action type="accept" label="Receive forwarded call on {{ a.88882.username }}"
                call_count="1"
                match_account="{{ a.88882.username }}"
                hangup="10"
                code="200" reason="OK"
                transport="{{ a.88882.transport }}"
                srtp="{{ a.88882.srtp }}"
                play="{{ c.play_file }}"
            />
            <action type="call" label="Call {{ a.90001.label }} -> {{ a.88881.label }}"
                transport="{{ a.90001.transport }}"
                expected_cause_code="200"
                caller="{{ a.90001.label }}@{{ c.domain }}"
                callee="{{ a.88881.label }}@{{ c.domain }}"
                from="sip:{{ a.90001.label }}@{{ c.domain }}"
                to_uri="{{ a.88881.label }}@{{ c.domain }}"
                max_duration="30" hangup="15"
                auth_username="{{ a.90001.username }}"
                password="{{ a.90001.password }}"
                realm="{{ c.domain }}"
                max_ring_duration="60"
                srtp="{{ a.90001.srtp }}"
                play="{{ c.play_file }}"
            />
            <action type="wait" complete="true" ms="60000"/>
        </actions>
    </section>
</config>
```

### 4. Call + media quality check

```xml
<config>
    <section type="voip_patrol">
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="call" label="Call echo service"
                transport="{{ a.88881.transport }}"
                expected_cause_code="200"
                caller="{{ a.88881.label }}@{{ c.domain }}"
                callee="11111@{{ c.domain }}"
                from="sip:{{ a.88881.label }}@{{ c.domain }}"
                to_uri="11111@{{ c.domain }}"
                max_duration="20" hangup="10"
                auth_username="{{ a.88881.username }}"
                password="{{ a.88881.password }}"
                realm="{{ c.domain }}"
                play="{{ c.play_file }}"
                rtp_stats="true"
                srtp="{{ a.88881.srtp }}"
                record="{{ scenario_name }}.wav"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox_st"
                file="{{ scenario_name }}.wav"
                length="9-11"
                sox_filter="maximum amplitude -ge 0.9; minimum amplitude -le -0.5"
            />
        </actions>
    </section>
</config>
```

### 5. Expect call to be rejected (blacklist / busy)

```xml
<config>
    <actions>
        <action type="codec" disable="all"/>
        <action type="codec" enable="pcma" priority="250"/>
        <action type="register" label="Register {{ a.88881.username }}"
            transport="{{ a.88881.transport }}"
            account="{{ a.88881.username }}"
            username="{{ a.88881.label }}"
            auth_username="{{ a.88881.username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ c.domain }}"
            expected_cause_code="200"
            srtp="{{ a.88881.srtp }}"
        />
        <action type="wait" complete="true" ms="2000"/>
        <!-- This action will PASS only if NO call is received -->
        <action type="accept"
            label="Verify 88881 receives NO call"
            call_count="1"
            match_account="{{ a.88881.username }}"
            fail_on_accept="true"
            transport="{{ a.88881.transport }}"
        />
        <!-- Caller expects a 486 Busy response -->
        <action type="call" label="Call blocked → 486"
            transport="{{ a.90001.transport }}"
            expected_cause_code="486"
            caller="{{ a.90001.label }}@{{ c.domain }}"
            callee="{{ a.88881.label }}@{{ c.domain }}"
            from="sip:{{ a.90001.label }}@{{ c.domain }}"
            to_uri="{{ a.88881.label }}@{{ c.domain }}"
            max_duration="10" hangup="5"
            auth_username="{{ a.90001.username }}"
            password="{{ a.90001.password }}"
            realm="{{ c.domain }}"
            max_ring_duration="10"
            srtp="{{ a.90001.srtp }}"
        />
        <action type="wait" complete="true" ms="15000"/>
    </actions>
</config>
```

---

## Common SIP response codes

| Code | Meaning in tests |
|------|-----------------|
| 200 | OK — call answered / register success |
| 401 | Unauthorized (auth challenge, usually register) |
| 403 | Forbidden |
| 404 | Not found |
| 407 | Proxy auth required |
| 408 | Request timeout |
| 486 | Busy here |
| 487 | Request terminated (CANCEL received) |
| 603 | Decline |

---

## Checklist: writing a new scenario

1. **Pick a filename** — prefix with a number so ordering is predictable (`NN-description.xml`).
2. **Check `config.yaml`** — make sure the accounts and databases you reference exist there.
3. **Add codecs** — put `codec disable="all"` + re-enables before any `register`/`call` when audio matters.
4. **Order matters inside voip_patrol:**
   - `codec` → `register` → `wait` (2 s) → `accept` → `call` → `wait complete`
   - `accept` must appear **before** its corresponding `call` (async setup).
5. **Wait at the end** — always finish with `<action type="wait" complete="true" ms="…"/>`. Use at least 2× the expected call duration.
6. **File names for recordings** — use `{{ scenario_name }}.wav` or `{{ scenario_name }}_1.wav` / `_2.wav` for multiple recordings; these are unique per scenario.
7. **Tag your scenario** if it belongs to a subset: `<config tag="smoke">`.
8. **Test it alone first:** `./run.sh NN-myscenario.xml`
