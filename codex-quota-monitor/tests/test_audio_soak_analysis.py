import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_audio_soak import analyze


class SoakAnalysisTests(unittest.TestCase):
    def evidence(self):
        report = {'status': 'finished', 'minutes': 120, 'preferences_restored': True,
                  'restore_errors': [], 'issues': [], 'samples': 1440,
                  'phases': [{'phase': n, 'transitions': 1, 'opens': 5,
                              'fade_seen': True, 'sleep_ended_seen': True} for n in range(4)]}
        rows = []
        for at in range(0, 7200, 5):
            rows.append({'elapsed_s': at, 'phase': at // 1800,
                         'resource': {'sampled_at_us': (at + 100) * 1000000,
                                      'internal_free_bytes': 20000, 'psram_free_bytes': 1000000,
                                      'cpu_percent': 40},
                         'audio': {'active': True, 'state': 'Playing', 'pcm_starvations': 0},
                         'ble': {'active': True, 'memory_rejections': 0}})
            if 2580 <= at < 2700:
                rows[-1]['audio']['sleep_gain_per_mille'] = 500
            if 2700 <= at < 3600:
                rows[-1]['audio'].update(state='SleepEnded', active=False)
        return report, rows

    def test_complete_evidence(self):
        self.assertTrue(analyze(*self.evidence())['passed'])

    def test_running_and_short_runs_never_pass(self):
        report, rows = self.evidence()
        report['status'] = 'running'
        self.assertFalse(analyze(report, rows)['passed'])
        report['status'] = 'finished'
        self.assertFalse(analyze(report, rows[:-1])['passed'])

    def test_missing_fade_and_sleep_not_accepted(self):
        report, rows = self.evidence()
        del report['phases'][1]['fade_seen']
        del report['phases'][1]['sleep_ended_seen']
        self.assertFalse(analyze(report, rows)['passed'])

    def test_clock_reset_or_pcm_starvation_fails(self):
        report, rows = self.evidence()
        reset = copy.deepcopy(rows)
        reset[-1]['resource']['sampled_at_us'] = 10
        self.assertFalse(analyze(report, reset)['passed'])
        rows[-1]['audio']['pcm_starvations'] = 1
        self.assertFalse(analyze(report, rows)['passed'])

    def test_guard_rejection_and_restore_failure_remain_failures(self):
        report, rows = self.evidence()
        rows[-1]['ble']['memory_rejections'] = 1
        self.assertFalse(analyze(report, rows)['passed'])
        rows[-1]['ble']['memory_rejections'] = 0
        report['restore_errors'] = [{'operation': 'volume'}]
        self.assertFalse(analyze(report, rows)['passed'])

    def test_driver_recovery_cannot_erase_recorded_error(self):
        report, rows = self.evidence()
        report['issues'] = [{'kind': 'eof_not_advanced', 'phase': 0}]
        report['phases'][0]['test_driver_recoveries'] = 1
        self.assertFalse(analyze(report, rows)['passed'])

    def test_sparse_snapshots_cannot_prove_two_hours(self):
        report, rows = self.evidence()
        sparse = rows[::120] + [rows[-1]]
        report['samples'] = len(sparse)
        self.assertFalse(analyze(report, sparse)['passed'])

    def test_stopped_audio_does_not_count_as_continuous_playback(self):
        report, rows = self.evidence()
        for row in rows:
            if row['phase'] == 2:
                row['audio'].update(active=False, state='Stopped')
        self.assertFalse(analyze(report, rows)['passed'])

    def test_sleep_flags_without_samples_do_not_pass(self):
        report, rows = self.evidence()
        for row in rows:
            if row['phase'] == 1:
                row['audio'].update(active=True, state='Playing', sleep_gain_per_mille=1000)
        self.assertFalse(analyze(report, rows)['passed'])

    def test_apps_only_run_is_labeled_and_checked_separately(self):
        report, rows = self.evidence()
        report.update(workload='apps', minutes=30, phases=[report['phases'][3]])
        rows = rows[-360:]
        for row in rows:
            row['elapsed_s'] -= 5400
        report['samples'] = len(rows)
        self.assertTrue(analyze(report, rows)['passed'])
        report['workload'] = 'full'
        self.assertFalse(analyze(report, rows)['passed'])


if __name__ == '__main__':
    unittest.main()
