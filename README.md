[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct.svg)](https://stand-with-ukraine.pp.ua)
<p align="center">
<img src="docs/images/logo.png" alt="VOLTSLogo" width="200"/>
</p>

**Voip Open Linear Tester Suite**

Functional tests for a VoIP systems based on [`voip_patrol`](https://github.com/igorolhovskiy/voip_patrol), [`sipp`](https://github.com/SIPp/sipp), [`sox`](https://sourceforge.net/projects/sox/), [`opensips`](https://opensips.org/), and [`docker`](https://www.docker.com/)

## 10'000 ft. view

The system is designed to run simple call scenarios, that you usually do with your desk phones.</br>
Scenarios are run one by one from `scenarios` folder in alphabetical order, which could be considered a limitation, but also allows you to reuse the same accounts in a different set of tests. This stands for `Linear` in the name ;)
So, call some destination(s) with one(or more) device(s) and control call arrival on another phone(s).</br>
But wait, there is more. VOLTS also can integrate with your MySQL and/or PostgreSQL databases to write some data there before the test and remove it after.</br>
Also, it can record (and play, obviously) media during the call and do media checks of these files (currently basic via [SoX](https://sox.sourceforge.net/))</br>
It will make and receive calls and configure the database. *It's not doing transfers at the moment. Sorry. I don't need em*</br>
And to add, you can definitely use it in [TDD](https://en.wikipedia.org/wiki/Test-driven_development) approach when adding functionalities to your existing PBX system. Test-Fail-Fix.</br></br>


The suite consists of 8 parts, that are running sequentially
1. Preparation - at this part we're transforming templates to real scenarios of `voip_patrol`, `sipp`, `database` and `media_check` using [`Jinja2`](https://jinja.palletsprojects.com/en/3.0.x/) template engine with [`jinja2_time`](https://github.com/hackebrot/jinja2-time) extension to put some dynamic data based on time.
2. Start of a `Websocket-TLS` proxy to provide possibility of use WSS transport for the `voip_patrol` scenarios.
---
3. Running database scripts. Usually - put some data inside some routing or subscriber data.
4. Running `voip_patrol` or `sipp` scenario.
5. Again running database scripts. Usually - remove data that had been put at stage 3.
6. Run `media_check` if necessary to analyse obtained media files
---
7. Tearing down a `Websocket-TLS` proxy.
8. Report - at this part we're analyzing the results of the previous steps reading and interpreting file obtained running steps 3-6. Printing results in the desired way. Table by default.
Steps 3-6 are running sequentially against scenarios files prepared in step 1. One at a time. Again, it's for `Linear`

## Building

Suite is designed to run locally from your Linux PC or Mac (maybe). And of course, `docker` should be installed. It's up to you.</br>
*Notes on using `podman`: I was able to run VOTLS using `podman-docker` package. One obstacle by default - the volumes permissions inside a container. To address this issue please refer to [this article](https://www.redhat.com/en/blog/container-permission-denied-errors).*</br>
To build, just run `./build.sh`. Script will build 6 `docker` images and tag em accordingly.</br>
In a case if `voip_patrol` or `sipp` is updated, you need to rebuild these containers again, you can do it with `./build.sh -r`

## Running

After building, just run
```sh
./run.sh
```
Simple, isn't it? This will run all scenarios found in `scenarios` folder one by one. To run a single scenario, run
```sh
./run.sh <scenario_name>
```
or
```sh
./run.sh scenarios/<scenario_name>
```
To get a set of tests running, usig `tag` keyword, see a how-to below
```sh
./run.sh tag=...
```
After running of the suite you can always find a `voip_patrol` presented results in `tmp/output` folder.

But simply run something blindly is boring, so before this, best to do some

## Configuration

We suppose to configure 2 parts here. First, and most complexes are

### Scenarios

`VOLTS` scenarios are combined `voip_patrol`/`sipp`, `database`, and `media_check` scenarios, that are just being templatized with `Jinja2` style. Mostly done not to repeat some passwords, usernames, domains, etc.</br>
Also, due to using `jinja2-time` extension, it's possible to use dynamic time/date values in your scenarios, for example testing some time-based rules on your PBX. For full documentation on how to use this type of data, please refer to [`jinja2-time`](https://github.com/hackebrot/jinja2-time) documentation.</br>
As you will see below, the core for all type of tests are actually `voip_patrol` or `sipp`, others are just helpers around.
#### Global config

Values for templates are taken from `scenarios/config.yaml`</br>
One thing to mention here, is that vars from `global` section transform to `c.` (for `config` or `g.` for `global`, `c.` and `.g` are equal) and from `accounts` to `a.` in templates for shorter notation.</br>
There is a special name `scenario_name` that is transforming to a scenario file name stripped `.xml` extension.</br>
Also, all settings from `global` section are inherited to the `accounts` section automatically unless they are defined there explicitly.</br>

`config.yaml`
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
  '90001':
    username:       '90001'
    auth_username:  '90001'
    password:       'SuperSecretPass3'
```
#### VoIP - patrol
To get most of it, please refer to [`voip_patrol`](https://github.com/igorolhovskiy/voip_patrol) config, but here follows some basic example to show the idea of the templating.</br></br>
**Make a register**
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
##### **Websocket transport notice.**
As `voip_patrol` itself is not supporting websocket transport, [`OpenSIPS`](https://opensips.org/) is used as a TLS-WSS SIP proxy. Using of it is simple, you just specify `transport="wss"` in your `voip_patrol` section, but under the hood it's using combination of `tls` transport and `proxy` option, so you can't use `proxy` option along with WebSocket transport.</br>
There is also a possibility to debug what is passing the proxy as it posts `HEP` encapsulated SIP traffic on a localhost. You can capture it with [`sngrep`](https://github.com/irontec/sngrep) using

```sh
$ docker exec -it volts_opensips sngrep -L udp:127.0.0.1:8888
```
or
```sh
./run.sh sngrep
```
in a separate terminal window during running tests, or using local installation of `sngrep` with
```sh
$ sudo sngrep -L udp:127.0.0.1:8888 port 8888
```
where `8888` is the `OPENSIPS_HEPD_PORT` (can be configured with `--hepd-port` option).</br></br>
Point, you need to use `turn` section of your `voip_patrol` configuration to make sure media is passing. See the example below.

#### SIPP
You can just add your existing SIPP scenarios mainly unchanged and they would be run with the following command:
```sh
sipp <target> -sf <scenario.xml> -m 1 -mp <random_port> -i <container_ip>
```
**Send an OPTIONS**
```xml
<config tag="sipp">
    <!-- Tag this test as sipp -->
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
| Attribute | Description |
| --- | --- |
| `transport` | Actual transport SIPP will use. Values are `udp`(default), `tcp` or `tls`. |
| `socket_mode` | `single` (default) - with one socket for all calls or `multi` - with one socket for each call. |
| `target` | What you usually specify as target when running standalone SIPP. If transport is TLS and no port is specified, `5061` is appended by default. |
| `call_rate` | `-r` option in SIPP. Set the call rate (in calls per seconds). 10 by default. |
| `max_calls` | `-m` option in SIPP. Stop the test and exit when 'max_calls' calls are processed. 1 by default. |
| `max_concurrent_calls` | `-l` option in SIPP. Set the maximum number of simultaneous calls. 10 by default. |
| `total_timeout` | How long to wait for a test to preform in seconds. 600 (10 minutes) by default |


#### Database
Database config is also done in XML, section `database`. We have 2 `stage`s of database scripts.
| Stage | Description |
| --- | --- |
| `pre` | Launched before running `voip_patrol`. Usually stage to put some accounts data, routing, etc. |
| `post` | Obviously, running after `voip_patrol`. For cleanup data inserted in `pre` stage. |


So, inside the `database` action you specify the tables you're working with. Each `table` section has 4 attributes.
| Attribute | Description |
| --- | --- |
| `name` | Actually name of the table we're working with. |
| `type` | Could be `insert`, `replace` and `delete`. Forming actual `INSERT`, `REPLACE` and `DELETE` SQL statements for the database. |
| `continue_on_error` | Optional. Em.. ignore errors on performed actions and continue no matter what. By default database actions will be stopped after encountering the first error. |
| `cleanup_after_test` | Optional. Allows you not to write an explicit `post` stage for your `insert` types. Will automatically form `delete` type on `post` stage for all `insert` (but not `replace`) that were declared on `pre` stage |

**Make a register with the database**
```xml
<!-- Test simple register -->
<config>
    <section type="database">
        <actions>
             <!-- "sippproxydb" here is referring to an entity in "databases" from config.yaml. -->
            <action database="sippproxydb" stage="pre">
                <!-- what data are we gonna insert into the "subscriber" table? -->
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
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
#### Media check
You can analyze calls recording with various media tools. *Currently only SoX is supported.*</br>
Media check is also described in XML
| Attribute | Description |
| --- | --- |
| `type` | Mandatory. Media check test to be performed. Currently only `sox`. |
| `file` | Mandatory. Path to file to check. Have to be aligned with `record` in one of `voip_patrol` actions. Best to have it with distinct names and currently with `/output/` prefix due to container interconnection (will be fixed later), see the example below for a better picture |
| `delete_after` | Do we delete file after media check? `yes`/`no`/`keep_failed`. `keep_failed` by default. This means we keep the file if the media test did not passed |
| `print_debug` | Print debug info on file on the console while testing. Useful for adjusting `filter` parameters. `yes`/`no`. `no` by default |
| `sox_filter` | Used if `type` is `sox`. Semicolon-separated expressions to test values obtained by SoX utility with the given file. Usually to check some float values like length or amplitude. See below more detailed description |

##### SoX media check
Within this check parameters from the `file` are collected by `sox` utility, more precisely - `sox --i <file>`, `sox <file> -n stat`, `sox <file> -n stats`.</br>
In a `sox_filter` attribute you can write a string to check some given values against collected parameters. All filter expressions should be true to test pass. Best to be explained on the example</br>
```
sox_filter="length s -ge 10; length s -le 11"
```
Here we have 1 parameter - `length s` that should be greater than or equal 10 and less than or equal 11. `length s` is one of the result parameters that are obtained by `sox <file> -n stats`.</br>
Point here is used not traditional `<=` style notation, but `bash` (`-eq` is `==`, `-lt` is `<`, `-gt` is `>`, `-le` is `<=`, `-ge` is `>=`, `-ne` is `!=`) style comparsion operators.
This is done due to traditional comparison symbols (`<`,`>`) are part of XML notation</br>
Getting parameters names is simple - they are converted from `sox` outputs, for example:
```
# sox 8000_12s.wav -n stats
DC offset  -0.000078    -> 'dc offset'     float
Min level  -0.321594    -> 'min level'     float
Max level   0.430359    -> 'max level'     float
Pk lev dB      -7.32    -> 'pk lev db'     float
RMS lev dB    -29.63    -> 'rms lev db'    float
RMS Pk dB     -16.78    -> 'rms pk db'     float
RMS Tr dB     -74.77    ...
Crest factor   13.04    ...
Flat factor     0.00    ...
Pk count           2    ...
Bit-depth      15/16    -> 'bit-depth'     string
Num samples     531k    -> 'num samples'   string
Length s      12.034    -> 'length s'      float
Scale max   1.000000    ...
Window s       0.050    ...
```
Here all parameter names are lowercase. One more example with the data above:
```
sox_filter="length s -ge 11; crest factor -lt 10; bit-depth -eq 15/16"
```
All number-like values are automatically treated as numbers and you can apply `-lt`, `-ge` type of comparisons.</br></br>
**Make a call to echo number and analyze the outcome**
```xml
<!-- Call echo service and name sure receive an answer -->
<config>
    <section type="voip_patrol">
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="call" label="Call to 11111 (echo)"
                transport="{{ a.88881.transport }}"
                <!-- We are expecting answer here -->
                expected_cause_code="200"
                caller="{{ a.88881.label }}@{{ c.domain }}"
                <!-- Setting R-URI -->
                callee="11111@{{ a.88881.domain }}"
                from="sip:{{ a.88881.label }}@{{ c.domain }}"
                to_uri="11111@{{ c.domain }}"
                max_duration="20" hangup="10"
                auth_username="{{ a.88881.username }}"
                password="{{ a.88881.password }}"
                realm="{{ c.domain }}"
                play="{{ c.play_file }}"
                rtp_stats="true"
                srtp="{{ a.88881.srtp }}"
                <!-- We heed to record file on an answer. To analyze it below now it MUST be with "/output/" path prefix -->
                record="/output/{{ scenario_name }}.wav"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox"
                sox_filter="length s -ge 10; length s -le 11"
                <!-- File name is the same as in the "record" attribute in the "call" action above. Now it MUST be with "/output/" path prefix -->
                file="/output/{{ scenario_name }}.wav"
            />
        </actions>
    </section>
</config>

```


### `run.sh` script

The `run.sh` script can be configured through command-line options (preferred) or environment variables:

#### Command Line Options (Recommended)
Use the command-line options described in the [Running](#running) section for most configuration needs.

#### Environment Variables
You can also set these environment variables to override default behavior:

| Variable name | Description |
| --- | --- |
|`REPORT_TYPE` | Report type provided at the end: `table`, `json`, `table_full`, `json_full`. Can be overridden with `-r/--report` option |
| `LOG_LEVEL` | `voip_patrol`/`sipp` log level on console (0-3). Can be overridden with `-l/--log-level` option |
| `MAX_SINGLE_TEST_TIME` | Maximum time single test is allowed to run in seconds. Can be overridden with `-t/--timeout` option |

#### Advanced Configuration
Additional variables for advanced users:
| Variable name | Description |
| --- | --- |
| `OPENSIPS_TLS_PORT` | OpenSIPS TLS port (default: 6051). Can be overridden with `--tls-port` option |
| `OPENSIPS_WSS_PORT` | OpenSIPS WSS port (default: 9443). Can be overridden with `--wss-port` option |
| `OPENSIPS_HEPS_PORT` | HEP source port (default: 8887). Can be overridden with `--heps-port` option |
| `OPENSIPS_HEPD_PORT` | HEP destination port (default: 8888). Can be overridden with `--hepd-port` option |

## Results

As a result, you will have a table like this.
```
+---------------------------------------+-----------------------------------------------------------+------+----------+-------+--------+------------------+
|                              Scenario |                                               VoIP Patrol | SIPP | Database | Media | Status |             Text |
+---------------------------------------+-----------------------------------------------------------+------+----------+-------+--------+------------------+
|                           01-register |                                                      PASS |  N/A |      N/A |   N/A |   PASS |  Scenario passed |
|                                       |                                      Register 88881       |      |          |       |   PASS | Main test passed |
|                          02-call-echo |                                                      PASS |  N/A |      N/A |   N/A |   PASS |  Scenario passed |
|                                       |                                      Call to 11111 (echo) |      |          |       |   PASS | Main test passed |

....
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

Scenarios ['49-teams-follow-forward', '50-team-no-answer-forward'] are failed!
```
That means your system is not OK, or something need to be tuned with the tests.</br>
Not really much to describe here, just read info on the console

## Scenario Examples

Examples shown in this section can duplicate examples from the section above. For more examples, refer to the `scenarios` folder.</br>

### Make a successful register
 * Here we assume that account data is known to our target system, ex. PBX.
```xml
<config>
    <section type="voip_patrol">
        <actions>
            <action type="register" label="Register {{ a.88881.label }}"
                transport="{{ a.88881.transport }}"
                <!-- Account parameter is more used in receiving a call on this account later -->
                account="{{ a.88881.label }}"
                <!-- username would be a part of AOR - <sip:username@realm> -->
                username="{{ a.88881.username }}"
                <!-- auth_username would be used in WWW-Authorize procedure -->
                auth_username="{{ a.88881.auth_username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ a.88881.domain }}"
                <!-- We are expecting to get 200 code here, so REGISTER is successfull -->
                expected_cause_code="200"
            />
            <!-- Just wait 2 sec for all timeouts -->
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    </section>
</config>
```
* .. but what if we need to add account data to PBX dynamically? Assume, that we have a SIP Proxy as a target system here.
```xml
<!-- Test simple register -->
<config>
    <section type="database">
        <actions>
             <!-- "sippproxydb" here is referring to an entity in "databases" from config.yaml. "stage" is explained a bit below -->
            <action database="sippproxydb" stage="pre">
                <!-- what data are we gonna insert into the "subscriber" table? -->
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="voip_patrol">
        <actions>
            <action type="register" label="Register {{ a.88881.label }}"
                transport="{{ a.88881.transport }}"
                <!-- Account parameter is more used in receiving a call on this account later -->
                account="{{ a.88881.label }}"
                <!-- username would be a part of AOR - <sip:username@realm> -->
                username="{{ a.88881.username }}"
                <!-- auth_username would be used in WWW-Authorize procedure -->
                auth_username="{{ a.88881.auth_username }}"
                password="{{ a.88881.password }}"
                registrar="{{ c.domain }}"
                realm="{{ a.88881.domain }}"
                <!-- We are expecting to get 200 code here, so REGISTER is successfull -->
                expected_cause_code="200"
            />
            <!-- Just wait 2 sec for all timeouts -->
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    </section>
</config>
```

### Expect fail on register
We're deleting data the from database and restoring it afterward.
```xml
<config>
    <section type="database">
        <actions>
            <action database="sippproxydb" stage="pre">
                <table name="subscriber" type="delete" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
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
                <!-- We are expecting to get 407 code here, maybe your registrar sending 401 or 403 code. So - adjust it here. -->
                expected_cause_code="407"
            />
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    /section>
</config>
```

### Simple call scenario
Register with 1 account and make a call from `90001` to `88881`. Max wait time to answer - 15 sec, duration of connected call - 10 sec.</br>
Point we don't register account `90001` here, as we're not receiving calls on it, just need to provide credentials on INVITE.</br>
Also trick, `match_account` in `accept` perfectly links with `account` in `register`.
```xml
<config>
    <actions>
        <!-- As we're using call functionality here - define the list of codecs -->
        <action type="codec" disable="all"/>
        <action type="codec" enable="pcma" priority="250"/>
        <action type="codec" enable="pcmu" priority="249"/>
        <action type="codec" enable="opus" priority="248"/>
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
</config>
```
### Advanced call scenario
Register with 2 accounts and call from he third one, not answer on 1st and make sure we receive a call on the second. So, your PBX should be configured to make a Forward-No-Answer from `88881` to `88882`.</br>
Also make sure, that on `88882` we got the call from `90001` (based on CallerID).
```xml
<config>
    <actions>
        <action type="codec" disable="all"/>
        <action type="codec" enable="pcma" priority="250"/>
        <action type="codec" enable="pcmu" priority="249"/>
        <action type="codec" enable="opus" priority="248"/>
        <action type="register" label="Register {{ a.88881.label }}"
            transport="{{ a.88881.transport }}"
            account="{{ a.88881.label }}"
            username="{{ a.88881.username }}"
            auth_username="{{ a.88881.auth_username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ c.domain }}"
            expected_cause_code="200"
            srtp="{{ a.88881.srtp }}"
        />
        <action type="register" label="Register {{ a.88882.label }}"
            transport="{{ a.88882.transport }}"
            account="{{ a.88882.label }}"
            username="{{ a.88882.username }}"
            auth_username="{{ a.88882.auth_username }}"
            password="{{ a.88882.password }}"
            registrar="{{ c.domain }}"
            realm="{{ c.domain }}"
            expected_cause_code="200"
            srtp="{{ a.88882.srtp }}"
        />
        <action type="wait" complete="true" ms="2000"/>
        <action type="call" label="Call from 90001 to 88881->88882"
            transport="{{ a.90001.transport }}"
            expected_cause_code="200"
            caller="{{ a.90001.label }}@{{ c.domain }}"
            callee="88881@{{ c.domain }}"
            from="sip:{{ a.90001.label }}@{{ c.domain }}"
            to_uri="88881@{{ c.domain }}"
            max_duration="20" hangup="10"
            auth_username="{{ a.90001.username }}"
            password="{{ a.90001.password }}"
            realm="{{ c.domain }}"
            rtp_stats="true"
            <!-- Set some high ring timeout, so delayed forward will happen -->
            max_ring_duration="60"
            srtp="{{ a.90001.srtp }}"
            play="{{ c.play_file }}"
        />
        <action type="accept" label="Receive call on {{ a.88881.label }}"
            match_account="{{ a.88881.label }}"
            call_count="1"
            hangup="10"
            ring_duration="30"
            <!-- We're expecting a CANCEL here. And it's not optional -->
            cancel="force"
            transport="{{ a.88881.transport }}"
            srtp="{{ a.88881.srtp }}"
        />
        <action type="accept" label="Receive call on {{ a.88882.label }}"
            match_account="{{ a.88882.label }}"
            call_count="1"
            hangup="10"
            code="200" reason="OK"
            transport="{{ a.88882.transport }}"
            srtp="{{ a.88882.srtp }}"
            play="{{ c.play_file }}">
            <!-- Check that From header matching what we need. This way we can control CallerID. Adjust domain (and whole regex) accordingly -->
            <check-header name="From" regex="^.*sip:{{ a.90001.label }}@example\.com>.*$"/>
        </action>
        <action type="wait" complete="true" ms="20000"/>
    </actions>
</config>
```

### Advanced call scenario - 2. Now with databases.
Schema - SIP Proxy subscriber and then we have Asterisk behind as PBX.

`config.yaml`
```yaml
global:
  domain:           '<SIP_DOMAIN>'
  domain_wss:       '<SIP_WSS_DOMAIN>'
  transport:        'tls'
  srtp:             'sdes,force'
  dtls:             'dtls,force'
  stun_address:     'stun.ekiga.net:3478'
  play_file:        '/voice_ref_files/8000_2m30.wav'
  asterisk_context: 'default'
databases:
  'sippproxydb':
    type:       'mysql'
    user:       'sipproxyrw'
    password:   'sipproxyrwpass'
    base:       'sipproxy'
    host:       'mysipproxydb.local'
  'astdb':
    type:       'pgsql'
    user:       'asteriskrw'
    password:   'asteriskrwpass'
    base:       'asterisk'
    host:       'myasteriskdb.local'
accounts:
  '90011':
    username: '90011'
    password: 'SuperSecretPass1'
    ha1:      'SuperSecretHA1'
  '90012':
    username: '90012'
    password: 'SuperSecretPass2'
    ha1:      'SuperSecretHA2'
```
And now we need to populate all databases and make a call!
```xml
<!-- Register with 90012 and receive a call from 90011 -->
<config>
    <section type="database">
        <actions>
        <!-- add subscribers to sip proxy -->
            <action database="sippproxydb" stage="pre">
                <table name="subscriber" type="insert"  cleanup_after_test="true">
                    <field name="username" value="{{ a.90011.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="ha1" value="{{ a.90011.ha1 }}"/>
                    <!-- here password due to ha1 is useless, so we can put some data based on jinja2_time.TimeExtension (https://github.com/hackebrot/jinja2-time) -->
                    <field name="password" value="{% now 'local' %}"/>
                </table>
                <table name="subscriber" type="insert"  cleanup_after_test="true">
                    <field name="username" value="{{ a.90012.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="ha1" value="{{ a.90012.ha1 }}"/>
                    <field name="password" value="{% now 'local' + 'days=1', '%D' %}"/>
                </table>
            </action>
            <!-- add endpoints and aors to Asterisk -->
            <action database="astdb" stage="pre">
                <table name="ps_endpoints" type="insert"  cleanup_after_test="true">
                    <field name="id" value="{{ a.90011.label }}"/>
                    <field name="transport" value="transport-udp"/>
                    <field name="aors" value="{{ a.90011.label }}"/>
                    <field name="context" value="{{ c.asterisk_context }}"/>
                    <field name="disallow" value="all"/>
                    <field name="allow" value="!all,opus,alaw"/>
                    <field name="direct_media" value="no"/>
                    <field name="ice_support" value="no"/>
                    <field name="rtp_timeout" value="3600"/>
                </table>
                <table name="ps_aors" type="insert"  cleanup_after_test="true">
                    <field name="id" value="{{ a.90011.label }}"/>
                    <field name="contact" value="sip:{{ a.90011.label }}@{{ c.domain }}:5060"/>
                </table>
                <table name="ps_endpoints" type="insert"  cleanup_after_test="true">
                    <field name="id" value="{{ a.90012.label }}"/>
                    <field name="transport" value="transport-udp"/>
                    <field name="aors" value="{{ a.90012.label }}"/>
                    <field name="context" value="{{ c.asterisk_context }}"/>
                    <field name="disallow" value="all"/>
                    <field name="allow" value="!all,opus,alaw"/>
                    <field name="direct_media" value="no"/>
                    <field name="ice_support" value="no"/>
                    <field name="rtp_timeout" value="3600"/>
                </table>
                <table name="ps_aors" type="insert"  cleanup_after_test="true">
                    <field name="id" value="{{ a.90012.label }}"/>
                    <field name="contact" value="sip:{{ a.90012.label }}@{{ c.domain }}:5060"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="voip_patrol">
    <!-- Make a call from one endpoint to other -->
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="codec" enable="opus" priority="248"/>
            <action type="register" label="Register {{ a.90012.label }}"
                transport="{{ a.90012.transport }}"
                account="{{ a.90012.username }}"
                username="{{ a.90012.label }}"
                auth_username="{{ a.90012.username }}"
                password="{{ a.90012.password }}"
                registrar="{{ c.domain }}"
                realm="{{ c.domain }}"
                expected_cause_code="200"
                srtp="{{ a.90012.srtp }}"
            />
            <action type="wait" complete="true" ms="2000"/>
            <action type="accept" label="Receive call on {{ a.90012.label }} from {{ a.90011.label }}"
                call_count="1"
                match_account="{{ a.90012.username }}"
                hangup="10"
                code="200" reason="OK"
                transport="{{ a.90012.transport }}"
                srtp="{{ a.90012.srtp }}"
                play="{{ c.play_file }}">
                <check-header name="From" regex="^.*sip:{{ a.90011.label }}@.*$"/>
            </action>
            <action type="call" label="Call {{ a.90011.label }} -> {{ a.90012.label }}"
                transport="tls"
                expected_cause_code="200"
                caller="{{ a.90011.label }}@{{ c.domain }}"
                callee="{{ a.90012.label }}@{{ c.domain }}"
                from="sip:{{ a.90011.label }}@{{ c.domain }}"
                to_uri="{{ a.90012.label }}@{{ c.domain }}"
                max_duration="20" hangup="10"
                auth_username="{{ a.90011.username }}"
                password="{{ a.90011.password }}"
                realm="{{ c.domain }}"
                rtp_stats="true"
                max_ring_duration="15"
                srtp="{{ a.90011.srtp }}"
                play="{{ c.play_file }}"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
</config>
```
### Adding media check.

```xml
<!-- Call echo service and name sure receive an answer -->
<config>
    <section type="voip_patrol">
        <actions>
            <action type="codec" disable="all"/>
            <action type="codec" enable="pcma" priority="250"/>
            <action type="codec" enable="pcmu" priority="249"/>
            <action type="call" label="Call to 11111 (echo)"
                transport="{{ a.88881.transport }}"
                <!-- We are expecting answer here -->
                expected_cause_code="200"
                caller="{{ a.88881.label }}@{{ c.domain }}"
                <!-- Setting R-URI -->
                callee="11111@{{ a.88881.domain }}"
                from="sip:{{ a.88881.label }}@{{ c.domain }}"
                to_uri="11111@{{ c.domain }}"
                max_duration="20" hangup="10"
                auth_username="{{ a.88881.username }}"
                password="{{ a.88881.password }}"
                realm="{{ c.domain }}"
                play="{{ c.play_file }}"
                rtp_stats="true"
                srtp="{{ a.88881.srtp }}"
                <!-- We heed to record file on answer. To analyze it below now it MUST be with "/output/" path prefix -->
                record="/output/{{ scenario_name }}.wav"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox"
                <!-- We are testing that the outcome of the recorded file is between 10 and 11 seconds and checking amplitude -->
                sox_filter="length s -ge 10; length s -le 11; maximum amplitude -ge 0.9; minimum amplitude -le -0.5"
                <!-- File name is the same as in the "record" attribute in the "call" action above. Now it MUST be with "/output/" path prefix -->
                file="/output/{{ scenario_name }}.wav"
            />
        </actions>
    </section>
</config>
```
### Call to ECHO via WSS (WebSocket + DTLS), make sure media is received
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
                record="/output/{{ scenario_name }}.wav"
            />
            <action type="wait" complete="true" ms="30000"/>
        </actions>
    </section>
    <section type="media_check">
        <actions>
            <action type="sox"
                sox_filter="length s -ge 9; length s -le 11; maximum amplitude -ge 0.9; minimum amplitude -le -0.5"
                file="/output/{{ scenario_name }}.wav"
                print_debug="no"
                delete_after="yes"
            />
        </actions>
    </section>
</config>
```

### Running SIPP tests
```xml
<config>
    <section type="sipp">
        <actions>
            <action transport="{{ c.transport }}" target="{{ c.domain }}">
                <!-- sipp {{ c.domain }}:5061 -sf scen.xml -m 1 -r 1 -t ln -tls_cert /etc/ssl/certs/ssl-cert-snakeoil.pem -tls_key /etc/ssl/private/ssl-cert-snakeoil.key -->
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
Adding some auth to SIPP
```xml
<config>
    <section type="sipp">
        <actions>
            <action transport="{{ c.transport }}" target="{{ c.domain }}">
            ...
                <recv response="407" auth="true">
                </recv>

                <send>
                <![CDATA[

                    ACK sip:[service]@[remote_ip]:[remote_port] SIP/2.0
                    Via: SIP/2.0/[transport] [local_ip]:[local_port]
                    From: {{ a.88881.label }} <sip:{{ a.88881.label }}@[local_ip]:[local_port]>;tag=[call_number]
                    To: sut <sip:[service]@[remote_ip]:[remote_port]>[peer_tag_param]
                    Call-ID: [call_id]
                    CSeq: 1 ACK
                    Contact: sip:{{ a.88881.label }}@[local_ip]:[local_port]
                    Max-Forwards: 70
                    Content-Length: 0

                ]]>
                </send>

                <send retrans="500">
                <![CDATA[

                    INVITE sip:[service]@[remote_ip]:[remote_port] SIP/2.0
                    Via: SIP/2.0/[transport] [local_ip]:[local_port]
                    From: {{ a.88881.label }} <sip:{{ a.88881.label }}@[local_ip]:[local_port]>;tag=[call_number]
                    To: sut <sip:[service]@[remote_ip]:[remote_port]>
                    Call-ID: [call_id]
                    CSeq: 2 INVITE
                    Contact: sip:{{ a.88881.label }}@[local_ip]:[local_port]
                    [authentication username={{ a.88881.username }} password={{ a.88881.password }}]
                    Max-Forwards: 70
                    Content-Type: application/sdp
                    Content-Length: [len]

                    v=0
                    o=user1 53655765 2353687637 IN IP[local_ip_type] [local_ip]
                    s=-
                    t=0 0
                    c=IN IP[media_ip_type] [media_ip]
                    m=audio [media_port] RTP/AVP 0
                    a=rtpmap:0 PCMU/8000

                ]]>
                </send>
                ...
            </action>
        </actions>
    </section>
</config>
```
and some load as well. Why not?

*Note: this example in particular was to test push notification server, that's why it have iOS references*
```xml
<config>
    <section type="database">
        <actions>
             <!-- "sippproxydb" here is referring to an entity in "databases" from config.yaml. -->
            <action database="sippproxydb" stage="pre">
                <!-- what data are we gonna insert into the "subscriber" table? -->
                <table name="subscriber" type="insert" cleanup_after_test="true">
                    <field name="username" value="{{ a.88881.username }}"/>
                    <field name="domain" value="{{ c.domain }}"/>
                    <field name="password" value="{{ a.88881.password }}"/>
                </table>
            </action>
        </actions>
    </section>
    <section type="sipp">
        <actions>
            <action transport="{{ c.transport }}"
                    target="{{ c.domain }}"
                    max_calls="1000"
                    call_rate="10"
                    max_concurrent_calls="10"
                    socket_mode="single"
                >
                <scenario name="UAC REGISTER - UnREGISTER with Auth">
                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 1 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];pn-prid=EFFDB4D8C32F845036CA3555003D44E98C82EA3F8437BD3499D14A17B039D5B6:voip&FC86D3D61AAFCC5D18AAC9D4CEDC6C70505080693FD21D0E62B5061FD4516ADE:remote;pn-provider=apns;pn-param=ABCD1234.generic.linphone.voip&remote;pn-silent=1;pn-timeout=0;pn-msg-str=IM_MSG;pn-call-str=IC_MSG;pn-groupchat-str=GC_MSG;pn-call-snd=notes_of_the_optimistic.caf;pn-msg-snd=msg.caf;transport=[transport]>;+sip.instance="<urn:uuid:65f9b73f-d655-4dd3-8633-10d8122c5299>"
                            Max-Forwards: 70
                            Supported: replaces, outbound, gruu, path
                            User-Agent: LinphoneiOS/4.6.5 (iPhone) LinphoneSDK/5.2.45
                            Accept: application/sdp
                            Accept: text/plain
                            Accept: application/vnd.gsma.rcs-ft-http+xml
                            Expires: 60
                            Content-Length: 0

                        ]]>
                    </send>

                    <recv response="100" optional="true" rrs="true"></recv>

                    <recv response="401" auth="true"></recv>

                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 1 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];pn-prid=EFFDB4D8C32F845036CA3555003D44E98C82EA3F8437BD3499D14A17B039D5B6:voip&FC86D3D61AAFCC5D18AAC9D4CEDC6C70505080693FD21D0E62B5061FD4516ADE:remote;pn-provider=apns;pn-param=ABCD1234.generic.linphone.voip&remote;pn-silent=1;pn-timeout=0;pn-msg-str=IM_MSG;pn-call-str=IC_MSG;pn-groupchat-str=GC_MSG;pn-call-snd=notes_of_the_optimistic.caf;pn-msg-snd=msg.caf;transport=[transport]>;+sip.instance="<urn:uuid:65f9b73f-d655-4dd3-8633-10d8122c5299>"
                            Max-Forwards: 70
                            Supported: replaces, outbound, gruu, path
                            User-Agent: LinphoneiOS/4.6.5 (iPhone) LinphoneSDK/5.2.45
                            Accept: application/sdp
                            Accept: text/plain
                            Accept: application/vnd.gsma.rcs-ft-http+xml
                            Expires: 60
                            [authentication username={{ a.88881.username }} password={{ a.88881.password }}]
                            Content-Length: 0

                        ]]>
                    </send>

                    <recv response="100" optional="true"></recv>

                    <recv response="200" crlf="true"></recv>

                    <pause milliseconds="5000"/>

                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 1 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];pn-prid=EFFDB4D8C32F845036CA3555003D44E98C82EA3F8437BD3499D14A17B039D5B6:voip&FC86D3D61AAFCC5D18AAC9D4CEDC6C70505080693FD21D0E62B5061FD4516ADE:remote;pn-provider=apns;pn-param=ABCD1234.ch.cern.linphone.voip&remote;pn-silent=1;pn-timeout=0;pn-msg-str=IM_MSG;pn-call-str=IC_MSG;pn-groupchat-str=GC_MSG;pn-call-snd=notes_of_the_optimistic.caf;pn-msg-snd=msg.caf;transport=[transport]>;+sip.instance="<urn:uuid:65f9b73f-d655-4dd3-8633-10d8122c5299>"
                            Max-Forwards: 70
                            Supported: replaces, outbound, gruu, path
                            User-Agent: LinphoneiOS/4.6.5 (iPhone) LinphoneSDK/5.2.45
                            Accept: application/sdp
                            Accept: text/plain
                            Accept: application/vnd.gsma.rcs-ft-http+xml
                            Expires: 0
                            Content-Length: 0

                        ]]>
                    </send>

                    <recv response="100" optional="true" rrs="true"></recv>

                    <recv response="401" auth="true"></recv>

                    <send retrans="500">
                        <![CDATA[
                            REGISTER sip:{{ c.domain }}:[remote_port] SIP/2.0
                            Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
                            From: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}>;tag=[pid]VOLTsTag00[call_number]
                            To: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@{{ c.domain }}:[remote_port]>
                            Call-ID: {% now 'utc', '%H%M%S' %}///[call_id]
                            CSeq: 1 REGISTER
                            Contact: "VOLTS UAC TESTER" <sip:{{ a.88881.label }}@[local_ip]:[local_port];pn-prid=EFFDB4D8C32F845036CA3555003D44E98C82EA3F8437BD3499D14A17B039D5B6:voip&FC86D3D61AAFCC5D18AAC9D4CEDC6C70505080693FD21D0E62B5061FD4516ADE:remote;pn-provider=apns;pn-param=ABCD1234.ch.cern.linphone.voip&remote;pn-silent=1;pn-timeout=0;pn-msg-str=IM_MSG;pn-call-str=IC_MSG;pn-groupchat-str=GC_MSG;pn-call-snd=notes_of_the_optimistic.caf;pn-msg-snd=msg.caf;transport=[transport]>;+sip.instance="<urn:uuid:65f9b73f-d655-4dd3-8633-10d8122c5299>"
                            Max-Forwards: 70
                            Supported: replaces, outbound, gruu, path
                            User-Agent: LinphoneiOS/4.6.5 (iPhone) LinphoneSDK/5.2.45
                            Accept: application/sdp
                            Accept: text/plain
                            Accept: application/vnd.gsma.rcs-ft-http+xml
                            Expires: 0
                            [authentication username={{ a.88881.username }} password={{ a.88881.password }}]
                            Content-Length: 0

                        ]]>
                    </send>

                    <recv response="100" optional="true" rrs="true"></recv>
                    <recv response="200"></recv>

                    <!-- definition of the response time repartition table (unit is ms)   -->
                    <ResponseTimeRepartition value="10, 20, 30, 40, 50, 100, 150, 200"/>

                    <!-- definition of the call length repartition table (unit is ms)     -->
                    <CallLengthRepartition value="10, 50, 100, 500, 1000, 5000, 10000"/>

                </scenario>

            </action>
        </actions>
    </section>
</config>
```
### Running only selected tests.
You can specify a `tag` on each test scenario, just adding an attribute to a `config` element.
```xml
<config tag='set1'>
    <section type="voip_patrol">
        ...
    </section>
</config>
```
Specify a tag by running
```sh
./run.sh tag=set1
```
In this case only tests that are holding this specific `tag` will be executed. And yes, in a `run.sh` you can specify as many tags as you want, using comma-separated list.
```sh
./run.sh tag=set1,set2,test_set3
```
