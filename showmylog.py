#!/usr/bin/env python3

import argparse
import sys
import os
from os.path import join as pjoin
from os.path import realpath, dirname
from datetime import date, time, timedelta, datetime
import typing
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from collections import OrderedDict

HOMEDIR = os.path.expanduser('~')
DEFAULT_REPORT_PATH = pjoin(HOMEDIR, 'mylog', 'report.html')
PATH_PATTERN = pjoin(HOMEDIR, 'mylog', '{}.mylog')

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TODAY_PATH = PATH_PATTERN.format(str(TODAY))
YESTERDAY_PATH = PATH_PATTERN.format(str(YESTERDAY))

CURDIR = dirname(realpath(__file__))

SP2TDDict = Dict[Tuple[str, str], timedelta]  # string-pair to timedelta dict

def t2dt(t: time) -> datetime:
    """ Convert a time object into a datetime object with some fixed date """
    return datetime.combine(date.min, t)


def parse_time(s: str) -> time:
    hour_str, min_str = s.replace('?', '0').replace('-', '0').split(':')
    return time(int(hour_str), int(min_str))


def parse_timedelta(s: str) -> timedelta:
    if s in ('--:--', '-:--'):
        return timedelta(0)
    hour_str, min_str = s.replace('?', '0').split(':')
    return timedelta(0, 3600 * int(hour_str) + 60 * int(min_str))


class Record:
    work_type = ':'
    start_time = time(0)
    end_time = time(0)
    penalty = timedelta(0)
    duration = timedelta(0)
    label = ''
    sublabel = ''

    format_str = 'Record(work_type={}, start_time={}, end_time={}, penalty={}, duration={}, label={}, sublabel={})'

    def __init__(self, words):
        # type: (Sequence[Union[str, time]]) -> None
        if len(words) == 2:
            self.start_time, self.end_time = typing.cast(Tuple[time, time], words)
            self.work_type = 'u'
            self.duration = t2dt(self.end_time) - t2dt(self.start_time)
        elif words:
            words = typing.cast(Sequence[str], words)
            self.work_type, start_time_str, end_time_str, penalty_str, duration_str, self.label, *rest = words
            self.start_time = parse_time(start_time_str)
            self.end_time = parse_time(end_time_str)
            if self.end_time == time(0):
                self.end_time = self.start_time
            self.penalty = parse_timedelta(penalty_str)
            self.duration = parse_timedelta(duration_str)
            if len(rest) >= 1:
                self.sublabel = rest[0]
            if t2dt(self.end_time) - t2dt(self.start_time) != self.duration:
                color_print("'{}' has incorrect duration".format(' '.join(words)), color='red')

    def __str__(self) -> str:
        return Record.format_str.format(repr(self.work_type), self.start_time, self.end_time, self.penalty,
            self.duration, repr(self.label), repr(self.sublabel))
    def __repr__(self) -> str:
        return str(self)

    def get_sublabel(self) -> str:
        if self.sublabel:
            return '{}: {}'.format(self.label, self.sublabel)
        else:
            return self.label


def parse_file(fname):
    # type: (str) -> List[Record]
    records = []  # type: List[Record]
    prev_record = None  # type: Optional[Record]
    with open(fname) as fobj:
        for line in fobj:
            words = line.split('#', maxsplit=1)[0].split()
            if words:
                if line.startswith(' '):
                    words = [':'] + words
                record = Record(words)
                if prev_record is not None:
                    ta = prev_record.end_time
                    tb = record.start_time
                    if ta < tb:
                        records.append(Record((ta, tb)))
                if record.end_time != record.start_time:
                    records.append(record)
                prev_record = record
    return records


def get_total_times(records, aggregate_by):
    # type: (Sequence[Record], str) -> SP2TDDict
    d = OrderedDict()  # type: SP2TDDict
    for record in records:
        if aggregate_by == 'work_type':
            key = record.work_type
        elif aggregate_by == 'label':
            key = record.label
        elif aggregate_by == 'sublabel':
            key = '{}.{}'.format(record.label, record.sublabel)
        else:
            raise Exception('aggregator {} not allowed'.format(repr(aggregate_by)))
        color = TYPE_COLOR.get(record.work_type, '')
        if (color, key) not in d:
            d[(color, key)] = timedelta(0)
        d[(color, key)] += record.duration
    return d


def table2strs(table, pad=' ', spad='', sep=' '):
    # type: (List[Tuple[str, List[str]]], str, str, str) -> List[Tuple[str, str]]
    lengths = []  # type: List[int]
    for (color, row) in table:
        for j, x in enumerate(row):
            if j + 1 > len(lengths):
                lengths += [0] * (j + 1 - len(lengths))
            lengths[j] = max(lengths[j], len(x) + len(spad))
    return [(color, sep.join([(x+spad).ljust(lengths[j], pad) for j, x in enumerate(row)])) for (color, row) in table]


with open(pjoin(CURDIR, 'style.css')) as fobj:
    STYLE = fobj.read()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title> mylog </title>
    <style>
{style}
    </style>
</head>
<body>
    <h1> mylog </h1>
    <ol>
{days}
    </ol>
</body>
</html>
"""


COLOR_CODES = {
    '': '\033[0m',
    'red': '\033[0;31m',
    'green':'\033[0;32m',
    'yellow':'\033[0;33m',
    'blue': '\033[0;34m',
    'magenta': '\033[0;35m',
    'cyan': '\033[0;36m',
    'white': '\033[0;37m',
}

TYPE_NAME = {'+': 'good', 's': 'sleep', '-': 'bad', '!': 'warn', ':': 'ok', 'u': 'uncounted', '': 'default'}
TYPE_COLOR = {'+': 'green', '-': 'red', '!': 'yellow', ':': '', 'u': '', '': '', 's': ''}


DAY_TEMPLATE = """
    <li>
        <p> {fpath}:<br />{start_time} to {end_time} = {total_time} </p>
        <div class="timeline timeline-small">
{agg_lines}
        </div>
        <div class="timeline timeline-big">
{lines}
        </div>
    </li>"""


LINE_TEMPLATE = """
    <div class="activity activity-{type} activity-big" style="flex: {ratio:.5f}">
    <span class="tooltiptext">{label}{begin} to {end} = {duration} ({percent:.1f} %)</span></div>"""

AGG_LINE_TEMPLATE = """
    <div class="activity activity-{type} activity-small" style="flex: {ratio:.5f}">
    <span class="tooltiptext">{type}<br />{duration} ({percent:.1f} %)</span></div>"""


def make_day_report(fpath, records, type_agg, start_time, end_time):
    # type: (str, Sequence[Record], SP2TDDict, time, time) -> str
    total_time = t2dt(end_time) - t2dt(start_time)
    lines = []
    for r in records:
        ratio = r.duration / total_time
        label = r.get_sublabel()
        if label:
            label += ':<br />'
        line = LINE_TEMPLATE.format(begin=r.start_time.strftime('%H:%M'),
            end=r.end_time.strftime('%H:%M'), duration=r.duration, type=TYPE_NAME.get(r.work_type, ''),
            ratio=ratio, percent=100*ratio, label=label)
        lines.append(line)
    agg_lines = []
    for (color, k), v in type_agg.items():
        ratio = v / total_time
        agg_lines.append(AGG_LINE_TEMPLATE.format(type=TYPE_NAME.get(k, ''), duration=v,
            ratio=ratio, percent=100*ratio))
    return DAY_TEMPLATE.format(fpath=fpath, total_time=total_time,
        start_time=start_time.strftime('%H:%M'), end_time=end_time.strftime('%H:%M'),
        lines=''.join(lines), agg_lines=''.join(agg_lines))


def pretty_str_timedelta(td, total_time, total_days=1):
    # type: (timedelta, timedelta, int) -> str
    hours = td.seconds // 3600
    days = td.days
    mins = (td.seconds // 60) % 60
    percent = 100 * td / total_time
    if days > 0:
        s = '{:3d}:{:02d}:{:02d} ({:5.1f} %)'.format(days, hours, mins, percent)
    else:
        s = '    {:2d}:{:02d} ({:5.1f} %)'.format(hours, mins, percent)
    if total_days > 1:
        td2 = td / total_days
        s += ' ({:01d}:{:02d} per day)'.format(td2.seconds // 3600, (td2.seconds // 60) % 60)
    return s


def color_print(*args, color='', file=sys.stdout, **kwargs):
    # type: (*Any, str, typing.TextIO, **Any) -> None
    if file.isatty():
        try:
            print(COLOR_CODES[color], file=file, end='', **kwargs)
            print(*args, file=file, **kwargs)
        finally:
            print(COLOR_CODES[''], file=file, end='', **kwargs)
    else:
        print(*args, file=file, **kwargs)


def add_to_dict(dest, source):
    # type: (Dict, Mapping) -> None
    for k, v in source.items():
        if k in dest:
            dest[k] += v
        else:
            dest[k] = v


def print_by_type_and_label(type_agg, label_agg, sort, short, days, total_time, time_limit=timedelta(0)):
    # type: (SP2TDDict, SP2TDDict, bool, bool, int, timedelta, timedelta) -> None
    print('By type:')
    print()
    items = type_agg.items()  # type: typing.Collection[Tuple[Tuple[str, str], timedelta]]
    if sort:
        items = sorted(items, reverse=True, key=(lambda x: x[1]))
    for (color, k), v in items:
        color_print(k, pretty_str_timedelta(v, total_time, days), color=color)
    print()

    print('By label:')
    print()
    items = label_agg.items()
    table = []
    if sort:
        items = sorted(items, reverse=True, key=(lambda x: x[1]))
    for (color, k), v in items:
        if v >= time_limit:
            table.append((color, [k, pretty_str_timedelta(v, total_time, days)]))
    for (color, l) in table2strs(table, '.', ' '):
        color_print(l, color=color)
    print()


def main():
    # type: () -> int

    parser = argparse.ArgumentParser(description='Show useful information about one or more *.mylog files')
    parser.add_argument('paths', nargs='*', default=['today'],
        help="""*.mylog files to show info about. Default is 'today'.
            Each argument should either be 'today', 'yesterday', a number or path to a file.
            A number k will be interpreted as a date k days before today.""")
    parser.add_argument('-r', '--report-path',
        help='report output path. Default is ~/mylog/report.html')
    parser.add_argument('-s', '--short', default=False, action='store_true',
        help="""print short output to stdout, i.e. when multiple days are passed as arguments,
            just print the aggregated summary instead of also printing output for each day separately.""")
    parser.add_argument('--sort', default=False, action='store_true',
        help='reverse sort output on stdout based on duration')
    args = parser.parse_args()  # type: Any

    if args.report_path is None:
        args.report_path = DEFAULT_REPORT_PATH
        os.makedirs(pjoin(HOMEDIR, 'mylog'), exist_ok=True)
    fpaths = []
    for x in args.paths:
        if x == 'today':
            fpaths.append(TODAY_PATH)
        elif x == 'yesterday':
            fpaths.append(YESTERDAY_PATH)
        elif x.isnumeric():
            fpaths.append(PATH_PATTERN.format(str(TODAY - timedelta(days=int(x)))))
        else:
            fpaths.append(x)

    type_aggs = {}  # type: SP2TDDict
    label_aggs = {}  # type: SP2TDDict
    day_reports = []  # type: List[str]
    total_total_time = timedelta(0)
    for fpath in fpaths:
        records = parse_file(fpath)
        min_time = records[0].start_time
        max_time = records[-1].end_time
        total_time = t2dt(max_time) - t2dt(min_time)
        total_total_time += total_time
        reported_time = sum((r.duration for r in records), timedelta())
        unreported_time = total_time - reported_time

        print(fpath)
        print()
        type_agg = get_total_times(records, 'work_type')
        add_to_dict(type_aggs, type_agg)
        label_agg = get_total_times(records, 'label')
        add_to_dict(label_aggs, label_agg)
        print_by_type_and_label(type_agg, label_agg, args.sort, args.short, 1, total_time)

        day_reports.append(make_day_report(fpath, records, type_agg, min_time, max_time))

    if len(fpaths) > 1:
        print('Summary:\n')
        print_by_type_and_label(type_aggs, label_aggs, args.sort, args.short, len(fpaths),
            total_total_time, timedelta(minutes=5) * len(fpaths))

    report = HTML_TEMPLATE.format(style=STYLE, days=''.join(day_reports))
    with open(args.report_path, 'w') as fobj:
        fobj.write(report)
    return 0

if __name__ == '__main__':
    sys.exit(main())
