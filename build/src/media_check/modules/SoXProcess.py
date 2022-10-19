import os.path
import subprocess
import time

class SoXProcess:
    '''
    Class for processing all sox-related media checks
    '''
    filename = None
    file_stats = {}
    condition_filter = set()

    def __init__(self, filename):

        if not os.path.exists(filename):
            raise Exception("File {} not found".format(filename))

        self.filename = filename

    def _run_sox(self, cmd, use_std_out = True):
        '''
        Runs `sox` with given `cmd` and depending on `use_std_out` returning or STDOUT or STDERR
        '''
        sox_cmd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while sox_cmd.poll() is None:
            time.sleep(0.02)

        sox_cmd_out, sox_cmd_err = sox_cmd.communicate()

        if sox_cmd.returncode != 0:
            raise Exception("Sox command exited abnormally: {}\nOut: {}\nErr: {}".format(sox_cmd.returncode, sox_cmd_out, sox_cmd_err))

        return sox_cmd_out if use_std_out else sox_cmd_err

    def _out_to_parameter_dict(self, sox_out):
        # Example data to process
        #
        # Samples read:            160000
        # Length (seconds):     10.000000
        # Scaled by:         2147483647.0
        # Maximum amplitude:     0.923492
        # Minimum amplitude:    -0.532257
        # Midline amplitude:     0.195618
        # Mean    norm:          0.057184
        # Mean    amplitude:     0.000158
        # RMS     amplitude:     0.104084
        # Maximum delta:         0.284180
        # Minimum delta:         0.000000
        # Mean    delta:         0.010176
        # RMS     delta:         0.020474
        # Rough   frequency:          500
        # Volume adjustment:        1.083
        #
        # This will go for a dict with {'parameter name': 'value'}

        result = {}
        sox_out_decoded = sox_out.decode("utf-8")

        for line in sox_out_decoded.split("\n"):
            try:
                param, value = line.rsplit(" ", 1)
            except ValueError:
                continue
            # Cleaning up parameter name "eg. 'RMS     amplitude:' -> 'rms amplitude'"
            param = " ".join(param.split()).lower()
            if param.endswith(":"):
                param = param[:-1]

            value = value.strip()
            # If param is number - use the number
            try:
                value = float(value)
            except ValueError:
                pass

            result[param] = value

        return result

    def _out_to_parameter_dict_info(self, sox_out):
        # Example data to process
        # Input File     : '/tmp/output/51-call-echo-media-control.wav'
        # Channels       : 1
        # Sample Rate    : 16000
        # Precision      : 16-bit
        # Duration       : 00:00:10.00 = 160000 samples ~ 750 CDDA sectors
        # File Size      : 320k
        # Bit Rate       : 256k
        # Sample Encoding: 16-bit Signed Integer PCM
        #
        # This will go for a dict with {'parameter name': 'value'}
        # A bit different function to process, just cause of separator is not space, but ":"

        result = {}
        sox_out_decoded = sox_out.decode("utf-8")

        for line in sox_out_decoded.split("\n"):
            try:
                param, value = line.split(":", 1)
            except ValueError:
                continue
            # Cleaning up parameter name "eg. 'Bit Rate       :' -> 'bit rate'"
            param = " ".join(param.split()).lower()
            if param.endswith(":"):
                param = param[:-1]

            value = value.strip()
            # If param is number - use the number
            try:
                value = float(value)
            except ValueError:
                pass

            result[param] = value

        return result

    def _set_file_stats(self):
        '''
        Run sox --i <filename>, sox <filename> -n stat, sox <filename> -n stats against a <filename>
        Get all outputed data and make a combined dict of gathered parameters
        '''
        if len(self.file_stats) > 0:
            return

        if self.filename == None:
            raise Exception("Filename to process is not set")

        cmd_stat    = ['/usr/bin/timeout', '10', '/usr/bin/sox', self.filename, '-n', 'stat']
        cmd_stats   = ['/usr/bin/timeout', '10', '/usr/bin/sox', self.filename, '-n', 'stats']
        cmd_info    = ['/usr/bin/timeout', '10', '/usr/bin/sox', '--i', self.filename]

        # sox stat and stats command giving the output to stderr. sox --i as usual to stdout
        sox_stat = self._run_sox(cmd_stat, use_std_out=False)
        sox_stats = self._run_sox(cmd_stats, use_std_out=False)
        sox_info = self._run_sox(cmd_info, use_std_out=True)

        sox_stat_dict = self._out_to_parameter_dict(sox_stat)
        sox_stats_dict = self._out_to_parameter_dict(sox_stats)
        sox_info_dict = self._out_to_parameter_dict_info(sox_info)

        result = {**sox_info_dict, **sox_stat_dict, **sox_stats_dict}

        self.file_stats = result

    def _process_single_valid_filter(self, single_condition, operator, operator_position):
        param = single_condition[:operator_position]
        param = " ".join(param.split()).lower()

        # Operator would be '__eq__', '__ge__', etc...
        operator = "__{}__".format(operator[1:])

        value = single_condition[operator_position + 3:]
        value = value.strip()

        try:
            value = float(value)
        except ValueError:
            pass

        return (param, operator, value)

    def _set_filter(self, filter_string):
        '''
        Convert line "A -ne 10; B -lt 10; G -eq This String" to
        set(('a', '__ne__', 10), ('b', '__lt__', 10), ('g', '__eq__', 'This String'))
        '''
        result = set()
        for condition in filter_string.split(';'):
            for operator in ('-eq', '-lt', '-gt', '-le', '-ge', '-ne'):
                operator_position = condition.find(operator)
                if operator_position != -1:
                    result.add(self._process_single_valid_filter(condition, operator, operator_position))
                    break

        self.condition_filter = result

    def get_file_stats(self):
        if len(self.file_stats) == 0:
            self._set_file_stats()

        return self.file_stats


    def apply_filter(self, filter):
        # Accepting as a value string with filter. All expressions should be TRUE to pass a test
        self._set_filter(filter)
        self._set_file_stats()

        error_result = []

        for condition in self.condition_filter:
            parameter, operator, value = condition
            if parameter not in self.file_stats:
                print("SoX Process warning: parameter <{}> not present in file stats".format(parameter))
                continue
            file_stats_value = self.file_stats[parameter]
            comparsion_function = getattr(file_stats_value, operator, None)

            if comparsion_function is None:
                print("SoX Process warning: operator <{}> is not supported".format(operator))

            if comparsion_function(value):
                continue

            faled_condition_desc = {
                'parameter': parameter,
                'operator': operator,
                'actual_value': file_stats_value,
                'expected_value': value
            }

            error_result.append(faled_condition_desc)

        if len(error_result) == 0:
            return None

        return error_result
