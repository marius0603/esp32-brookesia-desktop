"""Suggest an RSSI cutoff from far-to-near phone GATT measurements."""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def load_samples(stream):
    csv_rows = csv.DictReader(stream)
    if csv_rows.fieldnames != ['distance_cm', 'rssi_dbm']:
        raise ValueError('CSV 标题应为 distance_cm,rssi_dbm')
    groups = defaultdict(list)
    for line, row in enumerate(csv_rows, 2):
        try:
            distance, rssi = int(row['distance_cm']), int(row['rssi_dbm'])
        except (TypeError, ValueError) as error:
            raise ValueError(f'第 {line} 行的距离或 RSSI 格式无效') from error
        if distance <= 0 or not -127 <= rssi < 0:
            raise ValueError(f'第 {line} 行的距离或 RSSI 超出范围')
        groups[distance].append(rssi)
    if not groups or any(len(values) < 12 for values in groups.values()):
        raise ValueError('每档距离至少需要 12 个有效读数')
    return groups


def suggest(groups, near_cm=10, margin_db=6):
    if near_cm not in groups:
        raise ValueError(f'需要在目标距离 {near_cm} 厘米处实测')
    near = [values for distance, values in groups.items() if distance <= near_cm]
    far = [values for distance, values in groups.items() if distance > near_cm]
    if not near or not far:
        raise ValueError('目标距离内外都需要实测数据')
    # Use the weakest close group and the strongest far group, including nearby outside points.
    near_low = min(percentile(values, .10) for values in near)
    far_high = max(percentile(values, .90) for values in far)
    gap = near_low - far_high
    cutoff = math.ceil((near_low + far_high) / 2)
    if gap < margin_db or any(
        all(sample >= cutoff for sample in values[start:start + 3])
        for values in far for start in range(len(values) - 2)
    ):
        return None, gap
    return cutoff, gap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', help='手机复制的 CSV 文件。用 - 从标准输入读取')
    parser.add_argument('--near-cm', type=int, default=10, help='目标投喂距离，默认 10 厘米')
    args = parser.parse_args()
    if args.near_cm <= 0:
        parser.error('--near-cm 必须大于零')
    try:
        if args.csv == '-':
            groups = load_samples(sys.stdin)
        else:
            with Path(args.csv).open(encoding='utf-8-sig', newline='') as stream:
                groups = load_samples(stream)
        cutoff, gap = suggest(groups, args.near_cm)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for distance in sorted(groups, reverse=True):
        values = groups[distance]
        print(f'{distance:>3} cm | {len(values):>2} 次 | 中位数 {median(values):.1f} dBm | '
              f'P10 到 P90 {percentile(values, .10):.1f} 到 {percentile(values, .90):.1f} dBm')
    if cutoff is None:
        print(f'近远余量 {gap:.1f} dB。当前样本不支持可靠阈值，请调整手持方向后重测。')
        return 1
    print(f'建议阈值 {cutoff} dBm。按住期间连续 3 次达到该强度再触发。近远余量 {gap:.1f} dB。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
