"""Exercise real deep sleep with a fixed 20 second automatic recovery timer.

Does not reset the board, change the PIN, or change saved preferences.
"""
import json
from pathlib import Path
import time
import serial
from verify_child_mode import Client

ROOT=Path(__file__).resolve().parents[1]
KEYS=('auto_sleep_enabled','timeout_seconds','quiet_hours_enabled','quiet_start_minute','quiet_end_minute','resume_volume')


def main():
    report={'passed':False}
    with Client('COM5',timeout=25) as c:
        c.hello()
        before=c.call('DeviceModes','GetState',{})['result']
        report['before']={k:before[k] for k in KEYS}
        entries=before['deep_sleep']['entries']
        c.call('DeviceModes','TestDeepSleep',{})
    print('Deep sleep requested; waiting for the recovery timer and fresh boot',flush=True)
    started=time.monotonic()
    # Allow shutdown, the full timer interval and initial board startup.
    while time.monotonic()-started<27:
        time.sleep(1)
    deadline=started+95
    while time.monotonic()<deadline:
        try:
            with Client('COM5',timeout=4) as c:
                c.hello()
                after=c.call('DeviceModes','GetState',{})['result']
        except (OSError,serial.SerialException,TimeoutError):
            time.sleep(1)
            continue
        if after['deep_sleep']['error']:
            raise AssertionError(after['deep_sleep'])
        if after['deep_sleep']['entries']==entries:
            raise AssertionError('No deep-sleep entry recorded')
        assert after['deep_sleep']['entries']==entries+1,after['deep_sleep']
        assert after['deep_sleep']['wake_cause']==4,after['deep_sleep'] # ESP_SLEEP_WAKEUP_TIMER
        assert not after['deep_sleep']['pending'],after['deep_sleep']
        assert {k:after[k] for k in KEYS}==report['before']
        report.update({'passed':True,'deep_sleep':after['deep_sleep'],'elapsed_seconds':time.monotonic()-started})
        (ROOT/'runtime/deep-sleep-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Actual timer wake from deep sleep confirmed; preferences preserved',flush=True)
        return
    raise TimeoutError('Board did not return after the deep-sleep test')


if __name__=='__main__':
    main()
