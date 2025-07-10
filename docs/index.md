---
layout: default
title: Home
---

# VOLTS
{: .title.title--main}

## VoIP Open Linear Tester Suite
{: .title.title--little}

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct.svg)](https://stand-with-ukraine.pp.ua)

Functional tests for VoIP systems based on [`voip_patrol`](https://github.com/igorolhovskiy/voip_patrol), [`sipp`](https://github.com/SIPp/sipp), [`sox`](https://sourceforge.net/projects/sox/), [`opensips`](https://opensips.org/), and [`docker`](https://www.docker.com/).

## Overview
{: #overview .title}

The system is designed to run simple call scenarios, that you usually do with your desk phones. Scenarios are run one by one from `scenarios` folder in alphabetical order, which could be considered a limitation, but also allows you to reuse the same accounts in a different set of tests. This stands for `Linear` in the name 😉

So, call some destination(s) with one (or more) device(s) and control call arrival on another phone(s). But wait, there is more:

- **Database Integration**: VOLTS can integrate with your MySQL and/or PostgreSQL databases to write some data there before the test and remove it after
- **Media Recording & Analysis**: Record and play media during calls and perform media checks of these files (currently basic via [SoX](https://sox.sourceforge.net/))
- **TDD Support**: Use it in [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development) approach when adding functionalities to your existing PBX system. Test-Fail-Fix.

### System Architecture

The suite consists of 8 parts, running sequentially:

1. **Preparation** - Transform templates to real scenarios using [`Jinja2`](https://jinja.palletsprojects.com/en/3.0.x/) template engine with [`jinja2_time`](https://github.com/hackebrot/jinja2-time) extension
2. **WebSocket-TLS Proxy** - Start proxy to provide WSS transport for `voip_patrol` scenarios
3. **Database (Pre)** - Run database scripts to put test data
4. **VoIP Testing** - Run `voip_patrol` or `sipp` scenario
5. **Database (Post)** - Remove test data from databases
6. **Media Check** - Analyze obtained media files if necessary
7. **Proxy Teardown** - Stop WebSocket-TLS proxy
8. **Report Generation** - Analyze results and print them in desired format

Steps 3-6 run sequentially against scenario files prepared in step 1, one at a time. Again, it's for `Linear`.

## Getting Started
{: #getting-started .title}

### Building
{: #building .title.title--mini}

Suite is designed to run locally from your Linux PC or Mac. Docker should be installed.

**Notes on using `podman`**: VOLTS can run using `podman-docker` package. One obstacle by default - the volumes permissions inside a container. To address this issue please refer to [this article](https://www.redhat.com/en/blog/container-permission-denied-errors).

To build, just run:

```bash
./build.sh
```
{: .code}

Script will build 6 `docker` images and tag them accordingly.

In case if `voip_patrol` or `sipp` is updated, you need to rebuild these containers:

```bash
./build.sh -r
```
{: .code}

### Running
{: #running .title.title--mini}

After building, run all scenarios:

```bash
./run.sh
```
{: .code}

Simple, isn't it? This will run all scenarios found in `scenarios` folder one by one.

To run a single scenario:

```bash
./run.sh <scenario_name>
# or
./run.sh scenarios/<scenario_name>
```
{: .code}

To get a set of tests running using `tag` keyword:

```bash
./run.sh tag=set1,set2
```
{: .code}

#### Command Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message |
| `-l, --log-level N` | Set log level (0=silent, 1=normal, 2=verbose, 3=debug) |
| `-r, --report TYPE` | Set report type (table\|json\|table_full\|json_full) |
| `-t, --timeout N` | Set maximum single test time in seconds |
| `-v, --verbose` | Enable verbose output (equivalent to -l 2) |
| `-d, --debug` | Enable debug output (equivalent to -l 3) |
| `--tls-port N` | Set OpenSIPS TLS port |
| `--wss-port N` | Set OpenSIPS WSS port |
| `--heps-port N` | Set HEP source port |
| `--hepd-port N` | Set HEP destination port |
{: .table}

#### Special Commands

| Command | Description |
|---------|-------------|
| `stop` | Stop tests and delete all containers |
| `sngrep` | Launch SIP packet capture tool |
| `dbclean` | Clean up test data from databases |
{: .table}

After running the suite you can always find `voip_patrol` results in `tmp/output` folder.

## Configuration
{: #configuration .title}

### Scenarios
{: #scenarios .title.title--mini}

VOLTS scenarios are combined `voip_patrol`/`sipp`, `database`, and `media_check` scenarios, templatized with `Jinja2` style. This is done to avoid repeating passwords, usernames, domains, etc.

Due to using `jinja2-time` extension, it's possible to use dynamic time/date values in your scenarios, for example testing some time-based rules on your PBX.

### Global Config
{: #global-config .title.title--mini}

Values for templates are taken from `scenarios/config.yaml`. Variables from `global` section transform to `c.` (for `config`) and from `accounts` to `a.` in templates for shorter notation.

There is a special name `scenario_name` that transforms to a scenario file name stripped `.xml` extension.

All settings from `global` section are inherited to the `accounts` section automatically unless defined there explicitly.

**Example config.yaml:**

```yaml
global:
  domain:     '<SOME_DOMAIN>'
  transport:  'tls'
  srtp:       'dtls,sdes,force'
  play_file:  '/voice_ref_files/8000_12s.wav'
databases:
  'sipproxydb':
    type:       'mysql'
    user:       'sipproxydbrw'
    password:   'sipproxydbrwpass'
    base:       'sipproxydb'
    host:       'mysipproxydb.local'
accounts:
  '88881':
    username:       '88881'
    auth_username:  '88881-1'
    password:       'SuperSecretPass1'
  '88882':
    username:       '88882'
    auth_username:  '88882-67345'
    password:       'SuperSecretPass2'
```
{: .code}

### VoIP Patrol Configuration

#### Basic Registration Example

{% raw %}
```xml
<config>
    <section type="voip_patrol">
        <actions>
            <action type="register" label="Register {{ a.88881.label }}"
                transport="{{ a.88881.transport }}"
                account="{{ a.88881.label }}"
                username="{{ a.88881.username }}"
                auth_username="{{ a.88881.auth_username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ a.88881.domain }}"
                expected_cause_code="200"
            />
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

#### WebSocket Transport Notice

As `voip_patrol` itself doesn't support WebSocket transport, [`OpenSIPS`](https://opensips.org/) is used as a TLS-WSS SIP proxy. Using it is simple: specify `transport="wss"` in your `voip_patrol` section.

You can debug proxy traffic using [`sngrep`](https://github.com/irontec/sngrep):

```bash
./run.sh sngrep
# or
docker exec -it volts_opensips sngrep -L udp:127.0.0.1:8888
```
{: .code}

### SIPP Configuration

You can add existing SIPP scenarios mainly unchanged. They run with:

```bash
sipp <target> -sf <scenario.xml> -m 1 -mp <random_port> -i <container_ip>
```
{: .code}

**Example SIPP OPTIONS test:**

{% raw %}
```xml
<config tag="sipp">
    <section type="sipp">
        <actions>
            <action transport="{{ c.transport }}" target="{{ c.domain }}">
                <scenario name="Options">
                    <send>
                        <![CDATA[
                OPTIONS sip:check_server_health@{{ c.domain }} SIP/2.0
                Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                Max-Forwards: 70
                To: <sip:check_server_health@{{ c.domain }}>
                From: sipp <sip:check_server_health@[local_ip]:[local_port]>;tag=[call_number]
                Call-ID: [call_id]
                CSeq: 1 OPTIONS
                Contact: <sip:check_server_health@[local_ip]:[local_port]>
                Accept: application/sdp
                Content-Length: 0
                ]]>
                    </send>
                    <recv response="200" timeout="200"/>
                </scenario>
            </action>
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

#### SIPP Attributes

| Attribute | Description |
|-----------|-------------|
| `transport` | Transport SIPP will use: `udp` (default), `tcp`, or `tls` |
| `socket_mode` | `single` (default) or `multi` sockets |
| `target` | Target address (port 5061 appended for TLS if not specified) |
| `call_rate` | Call rate in calls per second (default: 10) |
| `max_calls` | Maximum number of calls (default: 1) |
| `max_concurrent_calls` | Maximum simultaneous calls (default: 10) |
| `total_timeout` | Test timeout in seconds (default: 600) |
{: .table}

### Database
{: #database .title.title--mini}

Database configuration is done in XML, section `database`. There are 2 stages:

| Stage | Description |
|-------|-------------|
| `pre` | Launched before running `voip_patrol`. Usually to put accounts data, routing, etc. |
| `post` | Running after `voip_patrol`. For cleanup data inserted in `pre` stage. |
{: .table}

#### Table Operations

| Attribute | Description |
|-----------|-------------|
| `name` | Table name |
| `type` | Operation: `insert`, `replace`, or `delete` |
| `continue_on_error` | Ignore errors and continue (optional) |
| `cleanup_after_test` | Auto-cleanup on post stage for insert operations (optional) |
{: .table}

**Example with Database:**

{% raw %}
```xml
<config>
    <section type="database">
        <actions>
            <action database="sippproxydb" stage="pre">
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="voip_patrol">
        <!-- VoIP Patrol configuration here -->
    </section>
</config>
```
{% endraw %}
{: .code}

### Media Check
{: #media-check .title.title--mini}

Analyze call recordings with media tools (currently only SoX is supported).

#### Media Check Attributes

| Attribute | Description |
|-----------|-------------|
| `type` | Media check type: currently only `sox` |
| `file` | Path to file (must use `/output/` prefix) |
| `delete_after` | Delete file after check: `yes`/`no`/`keep_failed` (default) |
| `print_debug` | Print debug info: `yes`/`no` (default) |
| `sox_filter` | Semicolon-separated expressions for SoX validation |
{: .table}

#### SoX Media Check

SoX collects parameters using `sox --i <file>`, `sox <file> -n stat`, and `sox <file> -n stats`.

**Filter example:**
```
sox_filter="length s -ge 10; length s -le 11; crest factor -lt 10"
```

This checks that:
- Length is between 10-11 seconds
- Crest factor is less than 10

Uses bash-style comparison operators (`-eq`, `-lt`, `-gt`, `-le`, `-ge`, `-ne`) instead of `<`, `>` symbols.

**Example with Media Check:**

{% raw %}
```xml
<config>
    <section type="voip_patrol">
        <actions>
            <!-- Call configuration with record="/output/{{ scenario_name }}.wav" -->
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox"
                sox_filter="length s -ge 10; length s -le 11"
                file="/output/{{ scenario_name }}.wav"
            />
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

## Examples
{: #examples .title}

### Basic Tests
{: #basic-tests .title.title--mini}

#### Simple Registration Test

{% raw %}
```xml
<config>
    <section type="voip_patrol">
        <actions>
            <action type="register" label="Register {{ a.88881.label }}"
                transport="{{ a.88881.transport }}"
                <!-- Account parameter is more used in receiving calls on this account later -->
                account="{{ a.88881.label }}"
                <!-- username would be a part of AOR - <sip:username@realm> -->
                username="{{ a.88881.username }}"
                <!-- auth_username would be used in WWW-Authorize procedure -->
                auth_username="{{ a.88881.auth_username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ a.88881.domain }}"
                <!-- We are expecting to get 200 code here, so REGISTER is successful -->
                expected_cause_code="200"
            />
            <!-- Just wait 2 sec for all timeouts -->
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

#### Basic Call Scenario

{% raw %}
```xml
<config>
    <section type="voip_patrol">
        <actions>
            <!-- As we're using call functionality here - define the list of codecs -->
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            
            <action type="register" label="Register {{ a.88881.label }}"
                transport="{{ a.88881.transport }}"
                account="{{ a.88881.label }}"
                username="{{ a.88881.username }}"
                auth_username="{{ a.88881.auth_username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ c.domain }}"
                expected_cause_code="200"
                <!-- Make sure we are using SRTP on a call received. This is done here as accounts are created before accept(answer) action -->
                srtp="{{ a.88881.srtp }}"
            />
            <action type="wait" complete="true" ms="2000"/>
            
            <action type="accept" label="Receive call on {{ a.88881.label }}"
                <!-- This is not a load test - so only 1 call is expected -->
                call_count="1"
                <!-- Make sure we have received a call on a previously registered account -->
                match_account="{{ a.88881.label }}"
                <!-- Hangup in 10 seconds after answer -->
                hangup="10"
                <!-- Send back "200 OK" -->
                code="200" reason="OK"
                transport="{{ a.88881.transport }}"
                <!-- Make sure we are using SRTP -->
                srtp="{{ a.88881.srtp }}"
                <!-- Play a file back to gather RTCP stats in the report -->
                play="{{ c.play_file }}"
            />
            
            <action type="call" label="Call {{ a.90001.label }} -> {{ a.88881.label }}"
                transport="tls"
                <!-- We are waiting for an answer -->
                expected_cause_code="200"
                caller="{{ a.90001.label }}@{{ c.domain }}"
                callee="{{ a.88881.label }}@{{ c.domain }}"
                from="sip:{{ a.90001.label }}@{{ c.domain }}"
                to_uri="{{ a.88881.label }}@{{ c.domain }}"
                max_duration="20" hangup="10"
                <!-- We are specifying all auth data here for INVITE -->
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
    </section>
</config>
```
{% endraw %}
{: .code}

### Advanced Scenarios
{: #advanced-scenarios .title.title--mini}

#### Call with Database Integration

{% raw %}
```xml
<!-- Register with 90012 and receive a call from 90011 -->
<config>
    <section type="database">
        <actions>
        <!-- add subscribers to sip proxy -->
            <!-- "sippproxydb" here is referring to an entity in "databases" from config.yaml. -->
            <action database="sippproxydb" stage="pre">
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.90011.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="ha1" value="{{ a.90011.ha1 }}"/>
                    <!-- here password due to ha1 is useless, so we can put some data based on jinja2_time.TimeExtension -->
                    <field name="password" value="{% now 'local' %}"/>
                </table>
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.90012.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="ha1" value="{{ a.90012.ha1 }}"/>
                    <field name="password" value="{% now 'local' + 'days=1', '%D' %}"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="voip_patrol">
        <!-- VoIP testing actions -->
    </section>
</config>
```
{% endraw %}
{: .code}

#### WSS Call with Media Check

{% raw %}
```xml
<!-- Call echo service and make sure receive an answer with media -->
<config>
    <section type="voip_patrol">
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="turn" enabled="true" server="{{ c.stun_address }}" stun_only="true"/>
            <action type="wait" ms="5000"/>
            
            <action type="call" label="Call to 11111 (echo) WSS"
                transport="wss"
                <!-- We are expecting answer here -->
                expected_cause_code="200"
                caller="{{ a.88881.label }}@{{ c.domain }}"
                callee="11111@{{ a.88881.domain_wss }}"
                from="sip:{{ a.88881.label }}@{{ c.domain }}"
                to_uri="11111@{{ c.domain }}"
                max_duration="20" hangup="10"
                auth_username="{{ a.88881.username }}"
                password="{{ a.88881.password }}"
                realm="{{ c.domain }}"
                play="{{ c.play_file }}"
                rtp_stats="true"
                srtp="{{ a.88881.dtls }}"
                <!-- We need to record file on answer. To analyze it below now it MUST be with "/output/" path prefix -->
                record="/output/{{ scenario_name }}.wav"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox"
                <!-- We are testing that the outcome of the recorded file is between 9 and 11 seconds and checking amplitude -->
                sox_filter="length s -ge 9; length s -le 11; maximum amplitude -ge 0.9"
                <!-- File name is the same as in the "record" attribute in the "call" action above. Now it MUST be with "/output/" path prefix -->
                file="/output/{{ scenario_name }}.wav"
                delete_after="yes"
            />
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

### SIPP Tests
{: #sipp-tests .title.title--mini}

#### Load Testing with SIPP

{% raw %}
```xml
<config>
    <section type="sipp">
        <actions>
            <action transport="{{ c.transport }}"
                    target="{{ c.domain }}"
                    max_calls="1000"
                    call_rate="10"
                    max_concurrent_calls="10"
                    socket_mode="single">
                <!-- sipp {{ c.domain }}:5061 -sf scen.xml -m 1000 -r 10 -l 10 -t ln -->
                <scenario name="UAC REGISTER - UnREGISTER with Auth">
                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 1 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];transport=[transport]>
                            Max-Forwards: 70
                            User-Agent: VOLTS/1.0
                            Expires: 60
                            Content-Length: 0

                        ]]>
                    </send>
                    <recv response="401" auth="true"></recv>
                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 2 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];transport=[transport]>
                            Max-Forwards: 70
                            User-Agent: VOLTS/1.0
                            Expires: 60
                            [authentication username={{ a.88881.username }} password={{ a.88881.password }}]
                            Content-Length: 0

                        ]]>
                    </send>
                    <recv response="200" crlf="true"></recv>
                    
                    <!-- Unregister -->
                    <pause milliseconds="5000"/>
                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 3 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];transport=[transport]>
                            Max-Forwards: 70
                            User-Agent: VOLTS/1.0
                            Expires: 0
                            Content-Length: 0

                        ]]>
                    </send>
                    <recv response="401" auth="true"></recv>
                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 4 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];transport=[transport]>
                            Max-Forwards: 70
                            User-Agent: VOLTS/1.0
                            Expires: 0
                            [authentication username={{ a.88881.username }} password={{ a.88881.password }}]
                            Content-Length: 0

                        ]]>
                    </send>
                    <recv response="200"></recv>
                </scenario>
            </action>
        </actions>
    </section>
</config>
```
{% endraw %}
{: .code}

#### Tagged Test Execution

You can specify a `tag` on each test scenario:

```xml
<config tag='set1'>
    <section type="voip_patrol">
        <!-- Test configuration -->
    </section>
</config>
```
{: .code}

Run tagged tests:

```bash
./run.sh tag=set1
./run.sh tag=set1,set2,test_set3
```
{: .code}

## Results
{: #results .title}

After running tests, you'll get a table like this:

```
+---------------------------------------+-----------------------------------------------------------+------+----------+-------+--------+------------------+
|                              Scenario |                                               VoIP Patrol | SIPP | Database | Media | Status |             Text |
+---------------------------------------+-----------------------------------------------------------+------+----------+-------+--------+------------------+
|                           01-register |                                                      PASS |  N/A |      N/A |   N/A |   PASS |  Scenario passed |
|                                       |                                      Register 88881       |      |          |       |   PASS | Main test passed |
|                          02-call-echo |                                                      PASS |  N/A |      N/A |   N/A |   PASS |  Scenario passed |
|                                       |                                      Call to 11111 (echo) |      |          |       |   PASS | Main test passed |
|            51-call-echo-media-control |                                                      PASS |  N/A |      N/A |  PASS |   PASS |  Scenario passed |
|                                       |                                      Call to 11111 (echo) |      |          |       |   PASS | Main test passed |
| 52-delayed-call-forward-unconditional |                                                      PASS |  N/A |     PASS |   N/A |   PASS |  Scenario passed |
|                                       |                                      Register 90012       |      |          |       |   PASS | Main test passed |
|                                       |                                      Register 90013       |      |          |       |   PASS | Main test passed |
|                                       |                      Receive call on 90012 and not answer |      |          |       |   PASS |    Call canceled |
|                                       |   Call from 90011 to 90012 (delay forward 25 sec) ->90013 |      |          |       |   PASS | Main test passed |
|                                       |                       Receive call on 90013       finally |      |          |       |   PASS | Main test passed |
|                53-server-check-health |                                                       N/A | PASS |      N/A |   N/A |   PASS | SIPP test passed |
+---------------------------------------+-----------------------------------------------------------+------+----------+-------+--------+------------------+
```
{: .code}

If any scenarios fail, you'll see:
```
Scenarios ['49-teams-follow-forward', '50-team-no-answer-forward'] are failed!
```

This means your system needs tuning or there are issues with the tests. Check the console output and logs in `tmp/output` folder for detailed information.

---

For more detailed examples and advanced configurations, refer to the `scenarios` folder in the repository.
