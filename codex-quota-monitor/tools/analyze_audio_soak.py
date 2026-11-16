"""Check soak evidence without confusing a running or incomplete test with a pass."""
import argparse
import json
from pathlib import Path


def analyze(report, rows):
    failures = list(report.get('issues', []))

    def require(condition, kind):
        if not condition:
            failures.append({'kind': kind})

    require(report.get('status') == 'finished', 'run_not_finished')
    require(report.get('preferences_restored') is True and not report.get('restore_errors'),
            'preferences_not_restored')
    require(bool(rows), 'samples_missing')
    require(len(rows) == report.get('samples'), 'sample_count_mismatch')
    duration = report.get('minutes', 120) * 60
    apps_only = report.get('workload') == 'apps'
    require(len(rows) >= duration / 30, 'sampling_coverage_insufficient')
    require(bool(rows) and rows[-1]['elapsed_s'] >= duration - 10, 'duration_incomplete')
    phases = {p['phase']: p for p in report.get('phases', [])}
    require(set(phases) == ({3} if apps_only else {0, 1, 2, 3}), 'phases_incomplete')
    for phase in (() if apps_only else (0, 2)):
        require(phases.get(phase, {}).get('transitions', 0) > 0,
                f'phase_{phase}_automatic_transition_not_observed')
        group = [r for r in rows if r['phase'] == phase]
        require(bool(group) and sum(bool(r['audio']['active']) for r in group) >= .9 * len(group),
                f'phase_{phase}_continuous_playback_not_observed')
        require(not phases.get(phase, {}).get('test_driver_recoveries'),
                f'phase_{phase}_required_driver_recovery')
    if not apps_only and duration / 4 >= 1000:
        for key in ('fade_seen', 'sleep_ended_seen'):
            require(phases.get(1, {}).get(key) is True, key + '_missing')
        group = [r for r in rows if r['phase'] == 1]
        require(any(0 <= r['audio'].get('sleep_gain_per_mille', 1000) < 1000 for r in group),
                'fade_samples_missing')
        ended = next((i for i, r in enumerate(group) if r['audio']['state'] == 'SleepEnded'), None)
        require(ended is not None and not any(r['audio']['active'] for r in group[ended:]),
                'sleep_stop_not_observed_or_restarted')
    require(phases.get(3, {}).get('opens', 0) >= 5, 'application_switching_incomplete')

    clocks = [r['resource']['sampled_at_us'] for r in rows]
    require(all(b > a for a, b in zip(clocks, clocks[1:])), 'device_clock_reset_or_stalled')
    require(not any(r['audio'].get('active') and r['audio'].get('pcm_starvations', 0)
                    for r in rows), 'active_pcm_starvation')
    require(all(isinstance(r['audio'].get('pcm_starvations'), int)
                for r in rows if r['audio']['active']), 'pcm_diagnostics_missing')
    if rows:
        initial_rejections = rows[0]['ble'].get('memory_rejections', 0)
        require(not any(r['ble'].get('memory_rejections', 0) > initial_rejections
                        for r in rows), 'new_ble_memory_rejection')
    stats = []
    for phase in range(4):
        group = [r for r in rows if r['phase'] == phase]
        if not group:
            continue
        stats.append({
            'phase': phase, 'samples': len(group),
            'first_elapsed_s': group[0]['elapsed_s'], 'last_elapsed_s': group[-1]['elapsed_s'],
            'internal_free_min': min(r['resource']['internal_free_bytes'] for r in group),
            'psram_free_min': min(r['resource']['psram_free_bytes'] for r in group),
            'cpu_percent_max': max(r['resource']['cpu_percent'] for r in group),
            'pcm_starvations_max': max(r['audio'].get('pcm_starvations', 0) or 0 for r in group),
            'write_gap_max_us': max(r['audio'].get('write_gap_max_us', 0) or 0 for r in group),
            'sleep_ended_samples': sum(r['audio']['state'] == 'SleepEnded' for r in group),
            'ble_active_samples': sum(bool(r['ble']['active']) for r in group),
        })
    gaps = [b['elapsed_s'] - a['elapsed_s'] for a, b in zip(rows, rows[1:])]
    require(max(gaps, default=0) <= 120, 'unobserved_interval_over_two_minutes')
    return {'passed': not failures, 'workload': report.get('workload', 'full'),
            'reported_failure_type': report.get('failure_type'),
            'failures': failures, 'phases': stats,
            'max_sample_gap_s': round(max(gaps, default=0), 2),
            'limits': ['muted_pcm_not_acoustic_test', 'no_phone_pairing_actions',
                       'no_radio_streams', 'no_speech_recognition',
                       'heap_minima_do_not_prove_absence_of_leaks']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    report = json.loads((args.folder / 'status.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (args.folder / 'samples.jsonl').read_text(encoding='utf-8').splitlines()]
    result = analyze(report, rows)
    (args.folder / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
