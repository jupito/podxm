"""Miscellaneous utility functionality."""

import datetime
import logging
import pprint
import shutil
import sys
import textwrap
import time
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from statistics import mean, median, stdev
from typing import Callable, List, Mapping, Sequence, TypeVar

import appdirs

import dateutil.parser

import pyutils.misc

T = TypeVar('T')
KT = TypeVar('KT')
log = logging.getLogger(__name__)


class AttrDict(dict):
    """Dictionary with attribute-like addressing."""
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class AppDirsPathlib(appdirs.AppDirs):
    """Convenience wrapper for AppDirs that returns Path objects."""
    def __getattribute__(self, name):
        r = super().__getattribute__(name)
        if name.endswith('_dir'):
            return Path(r)
        return r


class ParsedDatetime(datetime.datetime):
    """A datetime child class with more generic parsing."""
    @classmethod
    def parse(cls, s):
        """Parse string; return datetime or None if input is None."""
        def ensure_datetime(o):
            """Convert to datetime if needed."""
            if isinstance(o, datetime.datetime):
                return o
            return dateutil.parser.parse(o)

        if s is None:
            return None
        dt = ensure_datetime(s)
        return cls.fromtimestamp(dt.timestamp())

    def as_json(self):
        """Output as string to JSON stream."""
        return self.isoformat()


class Messager(object):
    """Message mediation."""
    def __init__(self, name='root', verbosity=0, sep=' ', end='\n',
                 file=sys.stdout, flush=False, truncate=False):
        self.name = name
        self.verbosity = verbosity
        self.sep = sep
        self.end = end
        self.file = file
        self.flush = flush
        self.truncate = truncate

    def msg(self, *args, **kwargs):
        """Print message."""
        if any(x not in self.__dict__ for x in kwargs):
            raise ValueError('Invalid keyword argument in %s', kwargs)
        d = dict(self.__dict__, **kwargs)
        value = d['sep'].join(str(x) for x in args)
        if d['truncate']:
            value = pyutils.misc.truncate(value)
        print(value, end=d['end'], file=d['file'], flush=d['flush'])

    def verbose(self, *args, **kwargs):
        """Print verbose message."""
        # TODO
        self.msg(*args, **kwargs)

    def feedback(self, *args, **kwargs):
        """Print feedback."""
        # TODO
        self.msg(*args, **kwargs)

    def pp(self, *args, **kwargs):
        """Pretty-print."""
        pprint.pprint(*args, stream=self.file, **kwargs)


class TerminalSizeMixin():
    """Mixin for TextWrapper that uses terminal size."""
    @staticmethod
    def _adjust(n, i):
        """Negative adjustment works like python indexing: -2 is 2nd-last."""
        if i < 0:
            return n + i + 1
        return n + i

    @property
    def width(self):
        return self._adjust(shutil.get_terminal_size().columns,
                            self.__dict__.get('width', 0))

    @width.setter
    def width(self, value):
        self.__dict__['width'] = value


class MultiWrapper(textwrap.TextWrapper, TerminalSizeMixin):
    """TextWrapper that can take several paragraphs as input, either as an
    iterable or a string (in which case each line is a paragraph).
    """
    def __init__(self, **kwargs):
        self.paragraph_indent = kwargs.pop('paragraph_indent', None)
        # if kwargs['width'] < 0:
        #     kwargs['width'] = (shutil.get_terminal_size().columns + 1 +
        #                        kwargs['width'])
        super().__init__(**kwargs)
        if self.paragraph_indent is None:
            self.paragraph_indent = self.subsequent_indent

    def wraps(self, text, title=None):
        """Multi-paragraph version of wrap()."""
        if not isinstance(text, str):
            text = str(text)
        text = text.splitlines() or ['']
        original_initial_indent = self.initial_indent
        if title is not None:
            diff = len(self.initial_indent) - len(title)
            if diff > 0:
                self.initial_indent = title + ' ' * diff
            elif len(text[0]) < self.width and len(text) == 1:
                self.initial_indent = title + ' '
            else:
                self.initial_indent = title + '\n' + original_initial_indent
        paragraphs = [self.fill(text.pop(0))]
        self.initial_indent = self.paragraph_indent
        paragraphs.extend(self.fill(x) for x in text if x)
        self.initial_indent = original_initial_indent
        return paragraphs

    def fills(self, text, title=None):
        """Multi-paragraph version of fill()."""
        return '\n'.join(self.wraps(text, title=title))


class HTMLStripper(HTMLParser):
    """HTML markup stripper."""
    def __init__(self):
        HTMLParser.__init__(self)
        self.fed = []

    def handle_data(self, data):
        self.fed.append(data)

    def error(self, message):
        raise Exception(message)

    def get_data(self):
        """Return processed text."""
        return ''.join(self.fed)

    @classmethod
    def strip(cls, text):
        """Strip markup from text, returning only the plaintext."""
        parser = cls()
        parser.feed(text)
        return parser.get_data()


def time_fmt(t=None, local=False, fmt='iso8601'):
    """Format time represented as seconds since the epoch."""
    formats = dict(
        iso8601='%Y-%m-%dT%H:%M %z',
        isofull='%Y-%m-%dT%H:%M:%S%z',
        isodate='%Y-%m-%d',
        rfc2822='%a, %d %b %Y %H:%M %z',
        locale='%c',
        )
    if fmt in formats:
        fmt = formats[fmt]
    if t is None:
        # t = time.time()
        return str(t)
    if isinstance(t, datetime.datetime):
        if fmt == 'compactdate':
            fmt = '%m-%d'
            if t.year != datetime.datetime.utcnow().year:
                fmt = '%Y-' + fmt
        return t.strftime(fmt)
    if isinstance(t, str):
        # Parse date from string.
        t = time.strptime(t)
    try:
        # Convert from seconds to tuple.
        if local:
            t = time.localtime(t)
        else:
            t = time.gmtime(t)
    except TypeError:
        # It's not a number, assume it's a time tuple already.
        pass
    return time.strftime(fmt, t)


def fmt_datetime(dt, fmt='iso8601'):
    """Format datetime."""
    formats = dict(
        iso8601='%Y-%m-%dT%H:%M %z',  # '%Y-%m-%dT%H:%M:%S%z'
        isodate='%Y-%m-%d',
        rfc2822='%a, %d %b %Y %H:%M %z',
        locale='%c',
        )
    if fmt in formats:
        fmt = formats[fmt]
    elif fmt == 'compactdate':
        now = datetime.datetime.utcnow()
        fmt = '%d'
        if (dt.year, dt.month) != (now.year, now.month):
            fmt = '%m-' + fmt
        if dt.year != now.year:
            fmt = '%Y-' + fmt
    return dt.strftime(fmt)


def fmt_duration(td):
    """Format media duration, represented by a timedelta."""
    # td = datetime.timedelta(seconds=td.seconds)  # Drop microseconds.
    # return str(td)
    if td is None:
        return '?:?'
    hours, secs = divmod(td.total_seconds(), 60**2)
    mins = round(secs / 60)
    return '{}:{:02}'.format(int(hours), mins)


def timedelta_stats(deltas, funcs=None):
    """Calculate statistic from a sequence of timedeltas."""
    if funcs is None:
        funcs = (min, median, max, mean, stdev)
    deltas_sec = [x.total_seconds() for x in deltas]
    return OrderedDict((f.__name__, datetime.timedelta(seconds=f(deltas_sec)))
                       for f in funcs)


def timedelta_floatdays(timedelta):
    """Return timedelta days as float."""
    return timedelta.total_seconds() / 60 / 60 / 24


def general_sort(lst: List[T], keys: Sequence[Callable[[T], KT]],
                 reverses: Sequence[bool]) -> List:
    """A more general version of list.sort() that supports a number of key
    functions with independent reverse flags.
    """
    # for key, reverse in zip(keys, reverses):
    #     values = sorted((key(x) for x in lst), reverse=reverse)
    #     indices.append({v: i for i, v in enumerate(values)})

    def indexmap(key: Callable[[T], KT], reverse: bool) -> Mapping[KT, int]:
        """Create mapping from key(item) to index when sorted."""
        values = sorted((key(x) for x in lst), reverse=reverse)
        return {v: i for i, v in enumerate(values)}
    maps = [indexmap(k, r) for k, r in zip(keys, reverses)]

    def final_key(entry: T) -> List[int]:
        """Construct sortkey for list.sort()."""
        return [m[k(entry)] for m, k in zip(maps, keys)]
    lst.sort(key=final_key)
    return lst
