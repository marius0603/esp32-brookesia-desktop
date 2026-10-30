"""Create a verified mono story copy without changing the original recording.

Detect severe stereo cancellation before loudness matching. Limit peaks at an
oversampled rate, then measure the actual encoded MP3 (not just pre-encode PCM).
Downloaded recordings and reports belong in private/ignored storage.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
METER = 'loudnorm=I=-14:TP=-2:LRA=7:print_format=json'


def execute(ffmpeg, source, audio_filter, destination=None):
    command = [str(ffmpeg), '-hide_banner', '-nostats', '-n', '-i', str(source),
               '-map', '0:a:0', '-vn', '-af', audio_filter]
    command += (['-c:a', 'libmp3lame', '-b:a', '96k', '-ar', '44100', '-ac', '1',
                 '-map_metadata', '0', str(destination)] if destination else ['-f', 'null', 'NUL'])
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:])
    return result.stderr


def run(ffmpeg, source, audio_filter, destination=None):
    """Read a loudnorm measurement; encoding uses execute() to avoid an extra normalization."""
    stderr = execute(ffmpeg, source, audio_filter, destination)
    matches = re.findall(r'\{[^{}]+"input_i"[^{}]+\}', stderr, re.S)
    if not matches:
        raise RuntimeError('FFmpeg did not return loudness measurements')
    return json.loads(matches[-1])


def decoded_duration(ffmpeg, source):
    command = [str(ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:0',
               '-ac', '1', '-ar', '16000', '-f', 's16le', '-']
    result = subprocess.run(command, capture_output=True, check=True)
    # A few source recordings contain malformed ID3 comments. They do not
    # change decoded audio; any actual decoder error still rejects the copy.
    warnings = result.stderr.decode('utf-8', errors='replace').strip().splitlines()
    if any(line not in ('Incorrect BOM value', 'Error reading comment frame, skipped') for line in warnings):
        raise RuntimeError('Audio decoder reported an error: ' + '\n'.join(warnings)[:1000])
    return len(result.stdout) / 32000


def normalize(ffmpeg, source, output, target):
    source, output = source.resolve(), output.resolve()
    if source == output or output.exists():
        raise ValueError('Keep the original and choose a new output file')
    if output.suffix.lower() != '.mp3':
        raise ValueError('The verified output must be an MP3 file')
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / 'codex-quota-monitor/runtime'):
        raise ValueError('Keep downloaded stories outside Git or in the ignored runtime folder')
    if not math.isfinite(target) or not -24 <= target <= -12:
        raise ValueError('Target loudness must be between -24 and -12 LUFS')
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    original_duration = decoded_duration(ffmpeg, source)
    stderr = execute(ffmpeg, source, METER)
    audio = next(line for line in stderr.splitlines() if 'Stream #' in line and 'Audio:' in line)
    stereo = bool(re.search(r'\bstereo\b', audio))
    if not stereo and not re.search(r'\bmono\b', audio):
        raise ValueError('Only mono/stereo story recordings are supported')
    downmix = 'pan=mono|c0=0.5*c0+0.5*c1' if stereo else 'pan=mono|c0=c0'
    before = run(ffmpeg, source, downmix + ',' + METER)
    selected, corrected = downmix, before
    cancellation = False
    if stereo:
        channels = [(f'pan=mono|c0=c{i}', run(ffmpeg, source, f'pan=mono|c0=c{i},' + METER)) for i in (0, 1)]
        best = max(channels, key=lambda x: float(x[1]['input_i']))
        if float(best[1]['input_i']) - float(before['input_i']) > 6:
            selected, corrected = best
            cancellation = True
    if not all(math.isfinite(float(corrected[k])) for k in ('input_i', 'input_tp')):
        raise ValueError('Source has no measurable audio')
    gain = target - float(corrected['input_i'])
    ceiling = -3.0
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='story-normalize-', dir=output.parent) as folder:
        for attempt in range(12):
            candidate = Path(folder) / f'pass-{attempt}.mp3'
            limit = 10 ** (ceiling / 20)
            chain = (selected + f',volume={gain:.5f}dB,aresample=192000,'
                     f'alimiter=limit={limit:.9f}:level=false:attack=5:release=100:latency=true,'
                     'aresample=44100')
            execute(ffmpeg, source, chain, candidate)
            after = run(ffmpeg, candidate, METER)
            error = target - float(after['input_i'])
            peak = float(after['input_tp'])
            if abs(error) <= 0.35 and peak <= -0.8:
                duration = decoded_duration(ffmpeg, candidate)
                if abs(duration - original_duration) > 0.05:
                    raise RuntimeError('Encoded audio duration changed; original unchanged')
                candidate.replace(output)
                break
            if peak > -0.8:
                ceiling -= peak + 1.1
            gain += max(-6, min(6, error * 2))
        else:
            raise RuntimeError('No copy passed encoded loudness/peak verification; original unchanged')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    report = {'input': str(source), 'input_sha256': original_hash, 'output': str(output),
              'target_lufs': target, 'mono_before': before, 'selected_before': corrected,
              'channel_filter': selected, 'stereo_cancellation_corrected': cancellation,
              'gain_db': gain, 'limiter_db': ceiling, 'after': after,
              'duration_seconds': round(duration, 3),
              'duration_difference_seconds': round(duration - original_duration, 4),
              'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix('.loudness.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lufs', type=float, default=-14)
    args = parser.parse_args()
    report = normalize(args.ffmpeg, args.input, args.output, args.lufs)
    print(json.dumps({'file': args.output.name, 'before_lufs': report['mono_before']['input_i'],
                      'after_lufs': report['after']['input_i'], 'true_peak_db': report['after']['input_tp'],
                      'stereo_cancellation_corrected': report['stereo_cancellation_corrected']}))


if __name__ == '__main__':
    main()
