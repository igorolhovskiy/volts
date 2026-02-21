import os.path
import subprocess
import time
import json


class Chromaprint:
    '''
    Class for processing all chromaprint-related media checks
    '''

    def __init__(self, filename: str):
        if not os.path.exists(filename):
            raise Exception(f"File {filename} not found")

        self.filename = filename
        self.fingerprint = []
        self.duration = ""

    def _run_fpcalc(self, cmd, use_std_out=True):
        '''
        Runs `fpcalc` with given `cmd` and depending on `use_std_out` returning or STDOUT or STDERR
        '''
        cmd_timeout = ['/usr/bin/timeout', '20'] + cmd

        fpcalc_cmd = subprocess.Popen(cmd_timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while fpcalc_cmd.poll() is None:
            time.sleep(0.02)

        fpcalc_cmd_out, fpcalc_cmd_err = fpcalc_cmd.communicate()

        # Ignore retcode 3 as it's Error decoding audio frame (End of file) - fine by me
        if fpcalc_cmd.returncode not in (0, 3):
            raise Exception(f"fpcalc command exited abnormally: {fpcalc_cmd.returncode}\nOut: {fpcalc_cmd_out}\nErr: {fpcalc_cmd_err}")

        return fpcalc_cmd_out if use_std_out else fpcalc_cmd_err

    def _set_fpcalc_fingerprint(self, length=0) -> list:

        fpcalc_cmd = [
            '/usr/bin/fpcalc',
            '-raw',
            '-json'
        ]
        if length > 0:
            fpcalc_cmd.extend(['-length', f"{length}"])
        fpcalc_cmd.append(self.filename)

        res = json.loads(self._run_fpcalc(fpcalc_cmd))
        self.fingerprint = res.get('fingerprint')
        self.duration = res.get('duration')

    def _compare_with_offset(self, fp2, max_offset=100):
        best_score = 0
        best_offset = 0

        fp1 = self.fingerprint
        if len(fp1) == 0:
            self._set_fpcalc_fingerprint()
            fp1 = self.fingerprint

        for offset in range(-max_offset, max_offset):
            if offset >= 0:
                a, b = fp1[offset:], fp2
            else:
                a, b = fp1, fp2[-offset:]

            length = min(len(a), len(b))
            if length < 10:  # need minimum overlap to be meaningful
                continue

            a, b = a[:length], b[:length]
            bits_diff = sum(bin(x ^ y).count('1') for x, y in zip(a, b))
            score = 1 - bits_diff / (length * 32)

            if score > best_score:
                best_score = score
                best_offset = offset

        return best_score, best_offset

    def _compare(self, fp2):

        fp1 = self.fingerprint
        if len(fp1) == 0:
            self._set_fpcalc_fingerprint()
            fp1 = self.fingerprint
        # Just truncate to shortest — works if content starts at same time
        length = min(len(fp1), len(fp2))
        fp1, fp2 = fp1[:length], fp2[:length]

        bits_diff = sum(bin(a ^ b).count('1') for a, b in zip(fp1, fp2))

        return 1 - bits_diff / (length * 32)

    def get_likeness(self, fingerprint: list, offset=0) -> tuple:

        fp2 = [int(f) for f in fingerprint if f.isdigit()]
        # If no fingerprint provided - files considered identical
        if len(fp2) == 0:
            return 100, 0

        if offset == 0:
            return self._compare(fp2), 0
        return self._compare_with_offset(fp2, offset)

    def get_duration(self):
        if self.duration == "":
            self._set_fpcalc_fingerprint()
        return self.duration
