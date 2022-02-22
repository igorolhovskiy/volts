# VOLTS

**Voip Open Linear Tester Suite**

Functional tests for VoIP systems based on [`voip_patrol`](https://github.com/igorolhovskiy/voip_patrol) and [`docker`](https://www.docker.com/)

## 10'000 ft. view

System is designed to run simple call scenarios, that you usually do with your desk phones.</br>
Scenarios are run one by one from `vp_scenarios` folder in alphabetical order, which could be considered as a limitation, but also allows you to reuse same accounts in a different set of tests. This stands for `Linear` in the name ;)
So, call some destination(s) with one(or more) device(s) and control call arrival on another phone(s).</br>
This tool would not configure your PBX to provide call flows, it's up to you. It will just make and receive calls, nothing more. *It also will not do transfers at the moment. Sorry*</br></br>

Suite consists of 3 parts, that are running sequentially
1. Preparation - at this part we're transforming templates to real scenarios using [`Jinja2`](https://jinja.palletsprojects.com/en/3.0.x/) template engine
2. Running `voip_patrol` against list of scenarios sequentially. One scenario at a time in alphabetical order.
3. Report - at this part we're analyzing results of previous step reading and interpreting file obtained at step 2. Printing results in a desired way. Table by default.
## Building

Suite is designed to run locally from your Linux PC or Mac. And of course, `docker` should be installed. It's up to you.</br>
To build, just run `./build.sh`. It would build 3 `docker` images and tag em accordingly.

## Running

After building, just run
```sh
./run.sh
```
Simple, isn't it? This will run all scenarios found in `vp_scenarios` folder one by one. To run single scenario, run
```sh
./run.sh <scenario_name>.xml
```
or
```sh
./run.sh vp_scenarios/<scenario_name>.xml
```
After running of the suite you can always find a `voip_patrol` presented results in `tmp/output` folder.

But simply run something blindly is boring, so before this best to do some

## Configuration

We suppose to configure 2 parts here. First, and most complex are

### Scenarios

`VOLTS` scenarios are `voip_patrol` scenarios, that are just being templatized with `Jinja2` style. Mostly done not to repeat some passwords, usernames, domains, etc.</br>
Values for templates are taken from `vp_scenarios/config.yaml`</br>
One thing to mention here, that vars from `global` section transforms to `c.` and from `accounts` to `a.` in templates for shorter notation.</br>
Also all settings from `global` section are inherited to `accounts` section automatically, unless they are defined there explicitly.</br>
To get most of it, please refer to [`voip_patrol`](https://github.com/https://github.com/igorolhovskiy/voip_patrol/voip_patrol) config, but here just some more basic examples.</br></br>
`config.yaml`
```yaml
global:
  domain:     '<SOME_DOMAIN>'
  transport:  'tls'
  srtp:       'dtls,sdes,force'
  play_file:  '/voice_ref_files/8000_12s.wav'
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
#### Make a successful register
```xml
<config>
    <actions>
        <action type="register" label="Register {{ a.88881.label }}"
            transport="{{ a.88881.transport }}"
            Account parameter is more used in receive call on this account later
            account="{{ a.88881.label }}"
            <!-- username would be a part of AOR - <sip:username@realm> -->
            username="{{ a.88881.username }}"
            <!-- auth_username would be used in WWW-Authorize procedure -->
            auth_username="{{ a.88881.auth_username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ a.88881.domain }}"
            <!-- We're expecting get 200 code here, so REGISTER is successfull -->
            expected_cause_code="200"
        />
        <!-- Just wait 2 sec for all timeouts -->
        <action type="wait" complete="true" ms="2000"/>
    </actions>
</config>
```
#### Expect fail on register
```xml
<config>
    <actions>
        <action type="register" label="Register {{ a.88881.label }}"
            transport="{{ a.88881.transport }}"
            account="{{ a.88881.label }}"
            username="{{ a.88881.username }}"
            auth_username="{{ a.88881.auth_username }}"
            password="{{ a.88881.password }}"
            registrar="{{ c.domain }}"
            realm="{{ a.88881.domain }}"
            <!-- We're expecting get 407 code here, maybe your registrar sending 401 or 403 code. So - adjust it here. -->
            expected_cause_code="407"
        />
        <action type="wait" complete="true" ms="2000"/>
    </actions>
</config>
```

#### Simple call scenario
Register with 1 account and make a call from `90001` to `88881`. Max wait time to answer - 15 sec, duration of connected call - 10 sec.</br>
Point, we don't register account `90001` here, as we're not receiving a calls on it, just need to provide credentials on INVITE.</br>
Also trick, `match_account` in `accept` perfectly links with `account` in `register`.
```xml
<config>
    <actions>
        <!-- As we're using call functionality here - define list of codecs -->
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
            <!-- Make sure we're using SRTP on a call receive. This is done here as accounts are created before accept(answer) action -->
            srtp="{{ a.88881.srtp }}"
        />
        <action type="wait" complete="true" ms="2000"/>
        <action type="accept" label="Receive call on {{ a.88881.label }}"
            <!-- This is not a load test - so only 1 call is expected -->
            call_count="1"
            <!-- Make sure we're received a call on a previously registered account -->
            match_account="{{ a.88881.label }}"
            <!-- Hangup in 10 seconds after answer -->
            hangup="10"
            <!-- Send back "200 OK" -->
            code="200" reason="OK"
            transport="{{ a.88881.transport }}"
            <!-- Make sure we're using SRTP -->
            srtp="{{ a.88881.srtp }}"
            <!-- Play some file back to gather RTCP stats in report -->
            play="{{ c.play_file }}"
        />
        <action type="call" label="Call {{ a.90001.label }} -> {{ a.88881.label }}"
            transport="tls"
            <!-- We're waiting for an answer -->
            expected_cause_code="200"
            caller="{{ a.90001.label }}@{{ c.domain }}"
            callee="{{ a.88881.label }}@{{ c.domain }}"
            from="sip:{{ a.90001.label }}@{{ c.domain }}"
            to_uri="{{ a.88881.label }}@{{ c.domain }}"
            max_duration="20" hangup="10"
            <!-- We're specifying all auth data here for INVITE -->
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
#### Advanced call scenario
Register with 2 accounts and call from third one, not answer on 1st and make sure we receive call on second. So, your PBX should be configured to make a Forward-No-Answer from `88881` to `88882`.</br>
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
            <check-header name="From" regex="^.*<sip:{{ a.90001.label }}@example\.com>.*$"/>
        </action>
        <action type="wait" complete="true" ms="20000"/>
    </actions>
</config>

```

### `run.sh` script

Not that much to configure here, mostly you'll be interested in setting environement variables at the start of the script
| Variable name | Description |
| --- | --- |
|`REPORT_TYPE` | Actually, report type, that would be provided at the end. </br>`table` - print results in table, only failed tests are pritend. </br>`json` - print results in JSON format, only failed tests are pritend. </br>`table_full`, `json_full` - prints results in table or JSON respectively, but print full info on tests passed
| `VP_LOG_LEVEL` | `voip_patrol` log level on the console |

## Results

As a results, you will have table like
```
+------------------------------------+-----------------------------------------------------------+--------+------------------+
|                           Scenario |                                                      Test | Status |             Text |
+------------------------------------+-----------------------------------------------------------+--------+------------------+
|                        01-register |                                                           |   PASS |  Scenario passed |
|                                    |                                      Register 88881-00001 |   PASS | Main test passed |
|                       02-call-echo |                                                           |   PASS |  Scenario passed |
|                                    |                                      Call to 11111 (echo) |   PASS | Main test passed |
|        03-register-wait-for-call-1 |                                                           |   PASS |  Scenario passed |
|                                    |                                      Register 88881-00001 |   PASS | Main test passed |
|                                    |                                Call to ##88881 from 88882 |   PASS | Main test passed |
|                                    |                                                   default |   PASS | Main test passed |
|        04-register-wait-for-call-2 |                                                           |   PASS |  Scenario passed |
|                                    |                                      Register 90002-00002 |   PASS | Main test passed |
|                                    |                                       Call 90001 -> 90002 |   PASS | Main test passed |
|                                    |                    Receive call on 90002-00002 from 90001 |   PASS | Main test passed |
|          05-immediate-call-forward |                                                           |   PASS |  Scenario passed |
|                                    |                                      Register 90002-00002 |   PASS | Main test passed |
|                                    |                           Call from 90001 to 91002->90002 |   PASS | Main test passed |
|                                    |                               Receive call on 90002-00002 |   PASS | Main test passed |
....
|    37-team-call-from-paused-member |                                                           |   PASS |  Scenario passed |
|                                    |                                      Register 90003-20614 |   PASS | Main test passed |
|                                    |                                      Register 90001-22466 |   PASS | Main test passed |
|                                    |                                      Register 90002-00002 |   PASS | Main test passed |
|                                    |                    Receive call on 90003-20614 and CANCEL |   PASS |    Call canceled |
|                                    |                      Call from team member 90001 -> 90543 |   PASS | Main test passed |
|                                    |                    Receive call on 90002-00002 and answer |   PASS | Main test passed |
+------------------------------------+-----------------------------------------------------------+--------+------------------+
All scenarios are OK!
```
Not really much to describe here, just read info on the console
