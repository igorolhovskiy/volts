[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct.svg)](https://stand-with-ukraine.pp.ua)
<p align="center">
<img src="docs/images/logo.png" alt="VOLTSLogo" width="200"/>
</p>

**Voip Open Linear Tester Suite**

Functional tests for VoIP systems based on [`voip_patrol`](https://github.com/igorolhovskiy/voip_patrol) and [`docker`](https://www.docker.com/)</br>
Some alternative introduction to the system can be found on [DOU](https://dou.ua/forums/topic/38567/)(ukrainian)

## 10'000 ft. view

System is designed to run simple call scenarios, that you usually do with your desk phones.</br>
Scenarios are run one by one from `scenarios` folder in alphabetical order, which could be considered as a limitation, but also allows you to reuse same accounts in a different set of tests. This stands for `Linear` in the name ;)
So, call some destination(s) with one(or more) device(s) and control call arrival on another phone(s).</br>
But wait, there is more. VOLTS also can integrate with your MySQL and/or PostgreSQL databases to write some data there before test and remove it after.</br>
It will make, receive calls and configure database. *It's not do transfers at the moment. Sorry. I don't need it*</br></br>

Suite consists of 4 parts, that are running sequentially
1. Preparation - at this part we're transforming templates to real scenarios of `voip_patrol` using [`Jinja2`](https://jinja.palletsprojects.com/en/3.0.x/) template engine with [jinja2_time](https://github.com/hackebrot/jinja2-time) extension to put some dynamic data based on time.
---
2. Running database scripts. Usually - put some data inside some routing or subscriber data.
3. Running `voip_patrol` against scenario.
4. Again running database scripts. Usually - remove data that had been put at the stage 2.
---
5. Report - at this part we're analyzing results of previous step reading and interpreting file obtained running step 3. Printing results in a desired way. Table by default.
Steps 2-4 are running sequentially against scenarios files prepared at step 1. One at a time.
## Building

Suite is designed to run locally from your Linux PC or Mac (maybe). And of course, `docker` should be installed. It's up to you.</br>
To build, just run `./build.sh`. It would build 4 `docker` images and tag em accordingly.</br>
In a case if `voip_patrol` is updated, you need to rebuild it's container again, you can do it with `./build.sh -r`

## Running

After building, just run
```sh
./run.sh
```
Simple, isn't it? This will run all scenarios found in `scenarios` folder one by one. To run single scenario, run
```sh
./run.sh <scenario_name>
```
or
```sh
./run.sh scenarios/<scenario_name>
```
After running of the suite you can always find a `voip_patrol` presented results in `tmp/output` folder.

But simply run something blindly is boring, so before this, best to do some

## Configuration

We suppose to configure 2 parts here. First, and most complex are

### Scenarios

`VOLTS` scenarios are combined `voip_patrol` and database-controlled scenarios, that are just being templatized with `Jinja2` style. Mostly done not to repeat some passwords, usernames, domains, etc.</br>
Also, due to using `jinja2-time` extension, it's possible to use dynamic time/date values in your scenarios, for example testing some time-based rules on your PBX. For full documentation on how to use this type of data, please refer to ['jinja2-time'](https://github.com/hackebrot/jinja2-time) documentation.</br>
Values for templates are taken from `scenarios/config.yaml`</br>
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
databases:
  'kamdb':
    type:       'mysql'
    user:       'kamailiorw'
    password:   'kamailiorwpass'
    base:       'kamailio'
    host:       'mykamailiodb.local'
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
 * Here we assume that account data is known to our PBX.
```xml
<config>
    <actions>
        <action type="register" label="Register {{ a.88881.label }}"
            transport="{{ a.88881.transport }}"
            <!-- "account" parameter is more used in receive call on this account later -->
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
* .. but what if we need to add account data to PBX dynamically? Assume, that we have Kamailio as a PBX here.
```xml
<!-- Test simple register -->
<config>
    <section type="database">
        <actions>
             <!-- "kamdb" here is referring to entity in "databases" from config.yaml. "stage" is explained a bit below -->
            <action database="kamdb" stage="pre">
                <!-- what data are we gonna insert into "subscriber" table? -->
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
                <!-- "account" parameter is more used in receive call on this account later -->
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
    </section>
</config>
```
Database config is also done in XML. We have 2 stages of database scripts.
* `pre` - Lauched before running `voip_patrol`. Usually stage to put some accounts data, routing, etc
* `post` - Obviously, running after `voip_patrol`. For cleanup data inserted in `pre` stage.
</br>

So, inside `database` action you specify tables you're working with. Each `table` secton have 4 attributes.

* `name` - actually name of table we're working with
* `type` - could be `insert`, `replace` and `delete`. Forming actually `INSERT`, `REPLACE` and `DELETE` SQL statements for database.
* `continue_on_error` - optional. Em.. ignore errors on preformed actions and continue no matter what. By default database actions will be stopped after encountering first error.
* `cleanup_after_test` - optional. Allows you not to write explicit `post` stage for your `insert` types. Will automatically form `delete` type on `post` stage for all `insert` (not `replace`) that were declared on `pre` stage.
#### Expect fail on register
We're deleting data from database and restoring it afterwards.
```xml
<config>
    <section type="database">
        <actions>
            <action database="kamdb" stage="pre">
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
                <!-- We're expecting get 407 code here, maybe your registrar sending 401 or 403 code. So - adjust it here. -->
                expected_cause_code="407"
            />
            <action type="wait" complete="true" ms="2000"/>
        </actions>
    /section>
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
            <check-header name="From" regex="^.*sip:{{ a.90001.label }}@example\.com>.*$"/>
        </action>
        <action type="wait" complete="true" ms="20000"/>
    </actions>
</config>
```

#### Advanced call scenario - 2. Now with databases.
Schema - Kamailio subscriber and than we have Asterisk behind as PBX.

`config.yaml`
```yaml
global:
  domain:           '<SOME_DOMAIN>'
  transport:        'tls'
  srtp:             'dtls,sdes,force'
  play_file:        '/voice_ref_files/8000_2m30.wav'
  asterisk_context: 'default'
databases:
  'kamdb':
    type:       'mysql'
    user:       'kamailiorw'
    password:   'kamailiorwpass'
    base:       'kamailio'
    host:       'mykamailiodb.local'
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
        <!-- add subscribers to Kamailio -->
            <action database="kamdb" stage="pre">
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
