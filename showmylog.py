#!/usr/bin/env python3

"""Show useful information about one or more *.mylog files."""

import argparse
import sys
import os
from os.path import join as pjoin
from os.path import realpath, dirname
from datetime import date, time, timedelta, datetime
import typing
from typing import Any, Dict, List, Mapping, MutableSequence, Optional, Sequence, Tuple, TypeVar
from collections import OrderedDict
import json

from jinja2 import Template

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
STALE_EXEMPT_TYPES = ['s', 'j']
TERM_RESET_COLOR_CODE = '\033[0m'
TERM_ERROR_COLOR_CODE = '\033[0;31m'  # red

HOMEDIR = os.path.expanduser('~')
DEFAULT_REPORT_PATH = pjoin(HOMEDIR, 'mylog', 'report.html')
PATH_PATTERN = pjoin(HOMEDIR, 'mylog', '{}.mylog')
TODAY_PATH = PATH_PATTERN.format(str(TODAY))
YESTERDAY_PATH = PATH_PATTERN.format(str(YESTERDAY))
CURDIR = dirname(realpath(__file__))

K = TypeVar('K')
addableV = TypeVar('addableV', timedelta, int)
SP2TDDict = Dict[Tuple[str, str], timedelta]  # string-pair to timedelta dict

errors = []
printed_now = False
style = None
activity_names = {}
activity_term_colors = {}
activity_web_colors = {}
activity_web_dark_colors = {}


def time_minus(a: time, b: time) -> datetime:
    """difference between times a and b"""
    return datetime.combine(date.min, a) - datetime.combine(date.min, b)


def add_to_dict(dest: Dict[K, addableV], source: Mapping[K, addableV]) -> None:
    for k, v in source.items():
        if k in dest:
            dest[k] += v
        else:
            dest[k] = v


def init_activity_and_color_info():
    with open(pjoin(CURDIR, 'colors.json')) as fp:
        color_info = json.load(fp)
    with open(pjoin(CURDIR, 'activity_types.json')) as fp:
        activity_info = json.load(fp)

    for activity_type, d in activity_info.items():
        if 'name' not in d:
            raise ValueError("activity_type '{}' has no name".format(activity_type))
        activity_names[activity_type] = d['name']
        if 'color' in d and d['color'] in color_info:
            ci = color_info[d['color']]
            if 'term' in ci:
                activity_term_colors[activity_type] = ci['term']
            if 'web' in ci:
                activity_web_colors[d['name']] = ci['web']
            if 'web.dark' in ci:
                activity_web_dark_colors[d['name']] = ci['web.dark']


def color_print(*args: Any, color_code: Optional[str] = None, file: typing.TextIO = sys.stdout,
        **kwargs: Any) -> None:
    if color_code and file.isatty():
        try:
            print(color_code, file=file, end='', **kwargs)
            print(*args, file=file, **kwargs)
        finally:
            print(TERM_RESET_COLOR_CODE, file=file, end='', flush=True, **kwargs)
    else:
        print(*args, file=file, **kwargs)


def print_error(*args: Any) -> None:
    errors.append(args)
    color_print(*args, file=sys.stderr, color_code=TERM_ERROR_COLOR_CODE)


def print_all_errors() -> None:
    for args in errors:
        color_print(*args, file=sys.stderr, color_code=TERM_ERROR_COLOR_CODE)


class Record:
    repr_str = ('Record(activity_type={}, start_time={}, end_time={}'
        ', penalty={}, duration={}, label={}, sublabel={})')

    def __init__(self, start_time: time, end_time: time, activity_type: str = 'u',
            penalty: timedelta = timedelta(0), duration: Optional[timedelta] = None,
            label: str = '', sublabel: str = '', words: Optional[Sequence[str]] = None):
        self.start_time = start_time
        self.end_time = end_time
        self.activity_type = activity_type
        self.penalty = penalty
        if duration is None:
            self.duration: timedelta = time_minus(end_time, start_time)
        else:
            self.duration = duration
        self.label = label
        self.sublabel = sublabel
        self.words = words

    def __str__(self) -> str:
        if self.words is None:
            return repr(self)
        else:
            return ' '.join(self.words)

    def __repr__(self) -> str:
        return Record.repr_str.format(repr(self.activity_type), self.start_time, self.end_time,
            self.penalty, self.duration, repr(self.label), repr(self.sublabel))

    def get_sublabel(self) -> str:
        if self.sublabel:
            return '{}: {}'.format(self.label, self.sublabel)
        else:
            return self.label


# PARSE (read input files and simultaneously check for inconsistencies/errors in input)

def parse_time(s: str) -> time:
    hour_str, min_str = s.replace('?', '0').replace('-', '0').split(':')
    return time(int(hour_str), int(min_str))


def parse_timedelta(s: str) -> timedelta:
    if s in ('--:--', '-:--'):
        return timedelta(0)
    hour_str, min_str = s.replace('?', '0').split(':')
    return timedelta(0, 3600 * int(hour_str) + 60 * int(min_str))


def parse_line(words: Sequence[str]) -> Record:
    activity_type, start_time_str, end_time_str, penalty_str, duration_str, label, *rest = words
    start_time = parse_time(start_time_str)
    end_time = parse_time(end_time_str)
    if end_time == time(0):
        end_time = start_time
    penalty = parse_timedelta(penalty_str)
    duration = parse_timedelta(duration_str)
    sublabel = rest[0] if rest else ''
    if time_minus(end_time, start_time) != duration:
        print_error("'{}' has incorrect duration".format(' '.join(words)))
    return Record(start_time, end_time, activity_type, penalty, duration, label, sublabel, words)


def parse_file(fname: str) -> List[Record]:
    records = []  # type: List[Record]
    prev_record = None  # type: Optional[Record]
    with open(fname) as fobj:
        for line in fobj:
            words = line.split('#', maxsplit=1)[0].split()
            if words:
                if line.startswith(' '):
                    words = ['u'] + words
                record = parse_line(words)
                if prev_record is not None:
                    ta = prev_record.end_time
                    tb = record.start_time
                    if ta < tb:
                        records.append(Record(ta, tb))
                records.append(record)
                prev_record = record
    return records


# PROCESS

def augment_records_with_current_time(records: MutableSequence[Record],
        stale_limit: float) -> None:
    now_ts = datetime.now()
    global printed_now
    if not printed_now:
        print('current time:', now_ts)
        printed_now = True

    last_record = records[-1]
    last_time = last_record.end_time
    now = now_ts.time()
    diff = time_minus(now, last_record.start_time)
    if now < last_time:
        return
    if last_record.activity_type == 'u' or (last_time == last_record.start_time):
        last_record.end_time = now
        last_record.duration = diff
    else:
        records.append(Record(last_time, now))
        diff = time_minus(now, last_time)
    if (stale_limit is not None and last_record.activity_type not in STALE_EXEMPT_TYPES and  # noqa
            diff > timedelta(minutes=stale_limit)):
        print_error("stale-limit reached for '{}'".format(str(last_record)))


def get_total_times(records: Sequence[Record], aggregate_by: Optional[str]) -> SP2TDDict:
    d = OrderedDict()  # type: SP2TDDict
    for record in records:
        if aggregate_by is None:
            key = 'total'
        elif aggregate_by == 'activity_type':
            key = record.activity_type
        elif aggregate_by == 'label':
            key = record.label
        elif aggregate_by == 'sublabel':
            key = '{}.{}'.format(record.label, record.sublabel)
        else:
            raise Exception('aggregator {} not allowed'.format(repr(aggregate_by)))
        if aggregate_by is None:
            activity_type = ''
        else:
            activity_type = record.activity_type
        if (activity_type, key) not in d:
            d[(activity_type, key)] = timedelta(0)
        d[(activity_type, key)] += record.duration
    return d


# OUTPUT

def table2strs(table: List[Tuple[str, List[str]]], pad: str = ' ', spad: str = '',
        sep: str = ' ') -> List[Tuple[str, str]]:
    lengths = []  # type: List[int]
    for (activity_type, row) in table:
        for j, x in enumerate(row):
            if j + 1 > len(lengths):
                lengths += [0] * (j + 1 - len(lengths))
            lengths[j] = max(lengths[j], len(x) + len(spad))
    return [(activity_type, sep.join([(x + spad).ljust(lengths[j], pad)
        for j, x in enumerate(row)])) for (activity_type, row) in table]


def get_style() -> str:
    global style
    if style is None:
        with open(pjoin(CURDIR, 'style.css')) as fobj:
            style = fobj.read()
    return style


class Ticks(typing.NamedTuple):
    n: int
    a_label: int
    d_label: int
    a_len: float
    d_len: float


def get_ticks(start_time: time, end_time: time) -> Ticks:
    total_time = time_minus(end_time, start_time)
    start_n = start_time.hour + (0 if start_time == time(hour=start_time.hour) else 1)
    end_n = end_time.hour

    if end_n < start_n:
        return Ticks(0, 0, 0, 0, 0)
    scale_factor = (end_n - start_n) // 10 + 1

    return Ticks(n=(end_n - start_n) // scale_factor + 1,
        a_label=start_n, d_label=scale_factor,
        a_len=time_minus(time(hour=start_n), start_time) / total_time,
        d_len=timedelta(hours=1) / total_time * scale_factor,
        )


def get_day_context(fpath: str, records: Sequence[Record], type_agg: SP2TDDict,
        start_time: time, end_time: time) -> Mapping[str, Any]:
    total_time = time_minus(end_time, start_time)
    return {
        'fpath': fpath,
        'total_time': total_time,
        'start_time': start_time.strftime('%H:%M'),
        'end_time': end_time.strftime('%H:%M'),
        'ticks': get_ticks(start_time, end_time),
        'agg_lines': [{
            'duration': pretty_str_timedelta_2(v),
            'ratio': v / total_time,
            'type': activity_names.get(k, 'unknown'),
            } for (activity_type, k), v in type_agg.items()],
        'lines': [{
            'duration': pretty_str_timedelta_2(r.duration),
            'ratio': r.duration / total_time,
            'label': r.get_sublabel(),
            'start_time': r.start_time.strftime('%H:%M'),
            'end_time': r.end_time.strftime('%H:%M'),
            'type': activity_names.get(r.activity_type, 'unknown'),
            } for r in records],
        }


def pretty_str_timedelta(td: timedelta, total_time: timedelta, total_days: int = 1) -> str:
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


def pretty_str_timedelta_2(td: timedelta) -> str:
    if td.days != 0:
        print_error("duration '{}' has days".format(timedelta))
    h = td.seconds // 3600
    m = (td.seconds // 60) % 60
    return '{:d}:{:02d}'.format(h, m)


def print_by_type_and_label(all_agg: SP2TDDict, type_agg: SP2TDDict, label_agg: SP2TDDict,
        sort: bool, long: bool, days: int,
        total_time: timedelta, time_limit: timedelta = timedelta(0)) -> None:

    items = all_agg.items()  # type: typing.Collection[Tuple[Tuple[str, str], timedelta]]
    for (activity_type, k), v in items:
        print('total:', pretty_str_timedelta(v, total_time, days))
    print()

    print('By type:')
    print()
    items = type_agg.items()
    if sort:
        items = sorted(items, reverse=True, key=(lambda x: x[1]))
    for (activity_type, k), v in items:
        color_print(k, pretty_str_timedelta(v, total_time, days),
            color_code=activity_term_colors.get(activity_type))
    print()

    print('By label:')
    print()
    items = label_agg.items()
    table = []
    if sort:
        items = sorted(items, reverse=True, key=(lambda x: x[1]))
    for (activity_type, k), v in items:
        if v >= time_limit:
            table.append((activity_type, [k, pretty_str_timedelta(v, total_time, days)]))
    for (activity_type, l) in table2strs(table, '.', ' '):
        color_print(l, color_code=activity_term_colors.get(activity_type))
    print()


def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', default=['today'],
        help="""*.mylog files to show info about. Default is 'today'.
            Each argument should either be 'today', 'yesterday', a number or path to a file.
            A number k will be interpreted as a date k days before today.""")
    parser.add_argument('-r', '--report-path',
        help='report output path. Default is ~/mylog/report.html')
    parser.add_argument('-l', '--long', default=False, action='store_true',
        help="""print long output to stdout when multiple days are passed as arguments""")
    parser.add_argument('--sort', default=False, action='store_true',
        help='reverse sort output on stdout based on duration')
    parser.add_argument('--use-now', default=False, action='store_true',
        help='Use current time as end time of last activity whose end time is not specified')
    parser.add_argument('--stale-limit', type=float,
        help='Raise error if log is staler than --stale-limit minutes')
    parser.add_argument('--refresh-time', default=None, type=int,
        help='HTML page refresh rate in seconds; no refresh if not specified')
    parser.add_argument('--ignore-missing', action='store_true', default=False,
        help="don't raise errors for missing or empty files")
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

    all_aggs = {}  # type: SP2TDDict
    type_aggs = {}  # type: SP2TDDict
    label_aggs = {}  # type: SP2TDDict
    total_total_time = timedelta(0)

    init_activity_and_color_info()
    report_context = {
        'style': get_style(),
        'refresh_time': args.refresh_time,
        'activity_web_colors': activity_web_colors,
        'activity_web_dark_colors': activity_web_dark_colors,
        'days': [],
    }  # type: Dict[str, Any]
    for fpath in fpaths:
        try:
            records = parse_file(fpath)
        except FileNotFoundError:
            if not args.ignore_missing:
                print_error("'{}' is '{}'".format(fpath, 'missing'))
            continue

        if args.use_now and records:
            augment_records_with_current_time(records, args.stale_limit)

        records = [record for record in records if record.start_time != record.end_time]
        if not records:
            if not args.ignore_missing:
                print_error("'{}' is '{}'".format(fpath, 'empty'))
            continue

        min_time = records[0].start_time
        max_time = records[-1].end_time
        total_time = time_minus(max_time, min_time)
        total_total_time += total_time
        # reported_time = sum((r.duration for r in records), timedelta())

        all_agg = get_total_times(records, None)
        add_to_dict(all_aggs, all_agg)
        type_agg = get_total_times(records, 'activity_type')
        add_to_dict(type_aggs, type_agg)
        label_agg = get_total_times(records, 'label')
        add_to_dict(label_aggs, label_agg)
        if args.long or len(fpaths) == 1:
            print(fpath)
            print()
            print_by_type_and_label(all_agg, type_agg, label_agg, args.sort, args.long,
                1, total_time)

        report_context['days'].append(get_day_context(
            fpath, records, type_agg, min_time, max_time))

    if len(fpaths) > 1:
        print('Summary:\n')
        print_by_type_and_label(all_aggs, type_aggs, label_aggs, args.sort, args.long, len(fpaths),
            total_total_time, timedelta(minutes=5) * len(fpaths))

    with open(pjoin(CURDIR, 'report.html.jinja2')) as fp:
        html_template = Template(fp.read())
    report = html_template.render(report_context)
    with open(args.report_path, 'w') as fobj:
        fobj.write(report)
    print_all_errors()
    return 1 if len(errors) > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
