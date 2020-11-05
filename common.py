"""Common functionality."""

import logging
import shlex
from pathlib import Path

from boltons.strutils import bytes2human, html2text, is_uuid
from boltons.timeutils import relative_time

import pyutils.files
import pyutils.misc
# from pyutils.misc import fmt_size

import jsonfile
import media
import util
from misctypes import Flag
from synd import Feed
from util import fmt_strings, fmt_duration, fmt_table, time_fmt

log = logging.getLogger(__name__)
messager = util.Messager(__name__)

WRAPPER = util.MultiWrapper(
    width=79,
    # width=-2,
    max_lines=20,
    break_long_words=False,
    break_on_hyphens=False,

    # initial_indent=' ' * 10,
    # subsequent_indent=' ' * 10,
    # paragraph_indent='\n' + ' ' * 10,

    # initial_indent=' ' * 10,
    # subsequent_indent=' ' * 10,
    # paragraph_indent=' ' * 12,

    initial_indent=' ' * 8,
    subsequent_indent=' ' * 4,
    paragraph_indent=' ' * 8,
)


class TextDict(dict):
    """Dictionary persistent in a text file."""
    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        self.read()

    # def __del__(self):
    #     self.write()

    # def __setitem__(self, key, value):
    #     super().__setitem__(key, value)
    #     self.write()

    def read(self):
        """Read from file, if it exists."""
        try:
            self.update(read_data(self.path))
        except FileNotFoundError:
            pass

    def write(self):
        """Write to file."""
        write_data(self.path, self)


def write_data(path, data):
    """Write object into JSON file."""
    pyutils.files.ensure_dir(path)
    with pyutils.files.tempfile_and_backup(path, 'w') as fp:
        return jsonfile.write_json(fp, data)


def read_data(path):
    """Read JSON file into dictionary."""
    with path.open() as fp:
        return jsonfile.read_json(fp)


class View(util.AttrDict):
    """A view to a feedlist. Giving '.' as flags stands for all flags."""
    DEFAULTS = dict(flags='foin', number=1, sortkey='fpD', sortkey2='SD')

    def __init__(self, directory=None, flags=None, number=None, sortkey=None,
                 sortkey2=None):
        super().__init__()
        self.directory = directory
        if self.directory is not None:
            self.directory = [Path(x) for x in self.directory]
        if flags is None:
            flags = self.DEFAULTS['flags']
        if number is None:
            number = self.DEFAULTS['number']
        if sortkey is None:
            sortkey = self.DEFAULTS['sortkey']
        if sortkey2 is None:
            sortkey2 = self.DEFAULTS['sortkey2']
        if flags == '.':
            flags = list(Flag)
        self.flags = [Flag(x) for x in flags]
        self.number = number
        self.sortkey = sortkey
        self.sortkey2 = sortkey2

    def __str__(self):
        s = '(f={flags}, n={number}, s={sortkey}, S={sortkey2}, {n})'
        d = dict(self, flags=''.join(x.value for x in self.flags),
                 n=len(self.directory))
        return s.format(**d)

    def parse(self, s, sep=','):
        """Parse view string, update original view, and create a new one."""
        if not s:
            s = ',,,'
        lst = list(s.split(sep))
        if len(lst) < 4:
            lst += [''] * (4 - len(lst))  # Fill in missing parts.
        try:
            flags, number, sortkey, sortkey2 = lst
        except ValueError:
            log.error('Cannot parse view: "%s"', s)
            raise
        return self.__class__(
            directory=self.directory,
            flags=flags or self.flags,
            number=int(number or self.number),
            sortkey=sortkey or self.sortkey,
            sortkey2=sortkey2 or self.sortkey2,
            )


# def message(value, *args, **kwargs):
#     """Print message."""
#     # print(value, *args, *kwargs)
#     messager.msg(value, *args, *kwargs)
#
#
# def feedback(value, *args, **kwargs):
#     """Print feedback."""
#     # print(value, *args, *kwargs)
#     messager.msg(value, *args, *kwargs)


def check_feed(feed, verbose=False):
    """Check feed. Return list of orphaned files."""
    for msg in feed.check(verbose=verbose):
        messager.msg(f'{feed}: {msg}')
    return feed.get_orphans()


def add_url(url):
    """Add feed. Return directory name."""
    feed = Feed(url)
    feed.refresh(force=True)
    # check_feed(feed)
    if feed.directory.exists():
        raise IOError(f'Feed directory exists: {feed.directory}')
    feed.write()
    check_feed(feed)
    return feed.directory


def show(header, seq, wrapper=WRAPPER):
    """Show bodies of text prettily, using a TextWrapper object."""
    if header:
        messager.msg(*header, sep=' ▶ ')
    # for text, title in seq:
    #     messager.msg(wrapper.fills(text, title+':'))
    rows = [[y+':', wrapper.fills(x)] for x, y in seq]
    messager.msg(fmt_table(rows))


def show_feed(feed, verbose=0):
    """Show feed."""
    header = [feed.directory, feed.url]
    lst = []
    if verbose:
        lst.extend([
            (time_fmt(feed.head.date, fmt='rfc2822'), 'Date'),
            (feed.priority, 'Priority'),
            (feed.head.link, 'Link'),
            (feed.url, 'Feed'),
            (feed.head.title, 'Title'),
            (feed.head.subtitle, 'Subt'),
            (feed.head.summary, 'Summ'),
            # (feed.head.language or 'unknown', 'Language'),
            # (', '.join(feed.get_tags().as_strings()) or [], 'Tags'),
            (str(feed.get_tags()), 'Tags'),
            (feed.head.image or [], 'Image'),
            (len(feed.entries), 'Entries'),
            ])
    if verbose > 1:
        # List flags and time range.
        def n_flagged(flag):
            return len(feed.list_entries(flags=flag.value))
        first = time_fmt(feed.entries[0].date, fmt='isodate')
        last = time_fmt(feed.entries[-1].date, fmt='isodate')
        lst.extend([
            (fmt_strings(f'{x.name} {n_flagged(x)}' for x in Flag), 'Flags'),
            (f'earliest {first}, latest {last}', 'Range'),
            ])
    show(header, lst)


def fmt_time(t):
    return fmt_strings([time_fmt(t, fmt='isofull'),
                        relative_time(t, ndigits=1) if t else '-'])


def show_entry(entry, verbose=0):
    """Show feed."""
    date_str = time_fmt(entry.date, fmt='isodate')
    header = [date_str, entry.feed.directory, entry.title]
    lst = []
    if verbose:
        lst.extend([
            (fmt_time(entry.date_published), "Publ'd"),
            (fmt_time(entry.date_seen), 'Seen'),
            # (entry.score, 'Score'),
            (fmt_strings([entry.flag.name, entry.progress, entry.score]),
             'FlPrSc'),
            (entry.guid + (' ok' if is_uuid(entry.guid) else ' bad'), 'GUID'),
            (entry.link, 'Link'),
            (entry.title, 'Title'),
            (entry.description(), 'Desc'),
            (str(entry.get_tags()), 'Tags'),
            ])
        for enc in entry.encs():
            lst.append((fmt_strings([bytes2human(enc.length or 0), enc.typ,
                                     enc.href]), 'URL'))
            try:
                lst.append((fmt_strings([bytes2human(enc.size() or 0),
                                         fmt_duration(enc.duration()),
                                         media.get_gain(enc.path),
                                         enc.filename]), 'File'))
            except FileNotFoundError:
                lst.append((enc.filename, 'File'))
            ##
            lst.append((enc.filename, '#Name'))
            # lst.append((enc.filename_slugified, '#Slug'))
            ##
            if verbose > 2:
                lst.extend([
                    (enc.expire_time(), 'Expire'),
                    (entry.subtitle, 'Subt'),
                    (html2text(entry.summary or ''), 'Summ'),
                    ])
    show(header, lst)
    # messager.msg(WRAPPER.fills(html2text(entry.summary or '')))


def show_files(entry, verbose=0):
    """Show files."""
    for enc in entry.encs():
        if verbose or enc.path.exists():
            print(shlex.quote(str(enc.path)))


def show_enclosure(enc):
    """Show enclosure."""
    if enc.path.exists():
        messager.msg('Media info:')
        messager.pp(media.get_media_info(enc.path))
        messager.msg('Extended attributes:')
        messager.pp(sorted(pyutils.files.XAttrStr(enc.path).items()))
    else:
        log.error('No file: %s', enc.path)


def show_enclosures(entry):
    """Show enclosure file info."""
    for enc in entry.encs():
        show_enclosure(enc)


def download_enclosure(enc, maxsize=None):
    """Download enclosure, return whether download was successful."""
    if enc.path.exists():
        log.debug('Already exists: %s', enc.path)
    elif enc.is_too_big(maxsize):
        log.warning('Download too big: %s: %s', bytes2human(enc.length or 0),
                    enc.path)
    else:
        # messager.msg(truncate('Downloading {}: {}'.format(
        #     fmt_size(enc.length), enc.path)))
        # messager.msg('Downloading {}: {}'.format(fmt_size(enc.length),
        #                                          enc.path), truncate=True)
        try:
            if enc.download():
                return True
            log.error('Download failed: %s', enc.path)
        except NotImplementedError:
            log.debug('Download not implemented: %s', enc)
        except KeyboardInterrupt:
            log.error('Download interrupted: %s', enc)
    return False


def download_enclosures(entry, maxsize=None):
    """Download entry enclosures."""
    for enc in entry.encs():
        if download_enclosure(enc, maxsize=maxsize):
            print(pyutils.misc.ring_bell(), flush=True)


def normalize_enclosure(enc, force=False):
    """Normalize enclosure."""
    if enc.path.exists():
        if force or not enc.is_normalized():
            media.normalize_volume(enc.path)


def normalize_enclosures(entry, force=False):
    """Normalize loudness in enclosures."""
    tags = entry.feed.get_tags()
    if force or 'nonorm' not in tags:
        for enc in entry.encs():
            normalize_enclosure(enc, force=force)


def play_enclosure(enc):
    """Play enclosure."""
    try:
        if enc.path.exists():
            exit_code = enc.play()
        else:
            messager.msg(f'File does not exist: {enc.path}')
            messager.msg(f'Streaming: {enc.href}')
            exit_code = enc.stream()
        messager.msg('Exit code:', exit_code)
        return exit_code
    except NotImplementedError:
        log.error('Play/stream not implemented: %s', enc)
        return None


def play_enclosures(entry, set_flag=True):
    """Play entry enclosures."""
    # exit_codes = (play_enclosure(x) for x in entry.encs())
    # if set_flag and all(x == 0 for x in exit_codes):
    #     if entry.flag in [Flag.fresh, Flag.important, Flag.new]:
    #         messager.msg('Flagging entry as opened')
    #         entry.set_flag(Flag.opened)
    #     entry.progress = 1  # TODO: Should be set correctly (embed mpv).
    if set_flag:
        if entry.flag in [Flag.fresh, Flag.important, Flag.new]:
            messager.msg('Flagging entry as opened')
            entry.set_flag(Flag.opened)
        entry.progress = 1  # TODO: Should be set correctly (embed mpv).
        entry.feed.write()
    exit_codes = [play_enclosure(x) for x in entry.encs()]
    return exit_codes


def remove_enclosure(enc):
    """Remove enclosure from disk."""
    if enc.path.exists():
        messager.msg('Removing:', enc.path)
        pyutils.files.trash_or_rm(enc.path)


def remove_enclosures(entry, set_flag=True):
    """Remove entry enclosures from disk."""
    for enc in entry.encs():
        remove_enclosure(enc)
    if set_flag:
        # if entry.flag == Flag.opened:
        #     entry.progress = 1
        entry.set_flag('d')


def drop_enc(entry):
    """Drop enclosure information from entry."""
    for enc in entry.encs():
        if enc.path.exists():
            raise FileExistsError(f'Enclosure exists: {enc.path}')
    del entry.enclosures
    entry.enclosures = []
    entry.feed.modified = True
