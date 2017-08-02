"""Common functionality."""

import logging
import shlex
from pathlib import Path

import jsonfile

import media

from misctypes import Flag

import pyutils.files
import pyutils.misc
from pyutils.misc import fmt_size

from synd import Feed

import util

log = logging.getLogger(__name__)
messager = util.Messager(__name__)

WRAPPER = util.MultiWrapper(
    # width=79,
    width=-2,
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
    """A view to a feedlist."""
    DEFAULTS = dict(flags='foin', sortkey='fpD', number=1, sortkey2='SD')

    def __init__(self, directory=None, flags=None, sortkey=None, number=None,
                 sortkey2=None):
        super().__init__()
        self.directory = directory
        if self.directory is not None:
            self.directory = [Path(x) for x in self.directory]
        if flags is None:
            flags = self.DEFAULTS['flags']
        if sortkey is None:
            sortkey = self.DEFAULTS['sortkey']
        if number is None:
            number = self.DEFAULTS['number']
        if sortkey2 is None:
            sortkey2 = self.DEFAULTS['sortkey2']
        self.flags = [Flag(x) for x in flags]
        self.sortkey = sortkey
        self.number = number
        self.sortkey2 = sortkey2

    def __str__(self):
        s = '(f={flags}, s={sortkey}, n={number}, S={sortkey2}, {n})'
        d = dict(self, flags=''.join(x.value for x in self.flags),
                 n=len(self.directory))
        return s.format(**d)

    def parse(self, s, sep=','):
        """Parse view string, update original view, and create a new one."""
        # lst = list(s.split(sep)) + [None] * 4  # Assure minimum length.
        flags, sortkey, number, sortkey2 = s.split(sep)
        return self.__class__(
            directory=self.directory,
            flags=flags or self.flags,
            sortkey=sortkey or self.sortkey,
            number=int(number or self.number),
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


def check_feed(feed):
    """Check feed. Return list of orphaned files."""
    for msg in feed.check():
        messager.msg('{}: {}'.format(feed, msg))
    return feed.get_orphans()


def add_url(url):
    """Add feed. Return directory name."""
    feed = Feed(url)
    feed.refresh(force=True)
    # check_feed(feed)
    if feed.directory.exists():
        raise IOError('Feed directory exists: {}'.format(feed.directory))
    feed.write()
    check_feed(feed)
    return feed.directory


def show(header, seq, wrapper=WRAPPER):
    """Show bodies of text prettily, using a TextWrapper object."""
    if header:
        messager.msg(*header, sep='\t')
    for text, title in seq:
        messager.msg(wrapper.fills(text, title+':'))


def show_feed(feed, verbose=0):
    """Show feed."""
    header = [feed.directory, feed.url]
    lst = []
    if verbose:
        lst.extend([
            (util.time_fmt(feed.head.date, fmt='rfc2822'), 'Date'),
            (feed.priority, 'Priority'),
            (feed.head.link, 'Link'),
            (feed.head.title, 'Title'),
            (feed.head.subtitle, 'Subtitle'),
            (feed.head.summary, 'Summary'),
            (feed.head.language or 'unknown', 'Language'),
            # (', '.join(feed.get_tags().as_strings()) or [], 'Tags'),
            (str(feed.get_tags()), 'Tags'),
            (feed.head.image or [], 'Image'),
            (len(feed.entries), 'Entries'),
            ])
    if verbose > 1:
        # List flags and time range.
        def n_flagged(flag):
            return len(feed.list_entries(flags=flag.value))
        first = util.time_fmt(feed.entries[0].date, fmt='isodate')
        last = util.time_fmt(feed.entries[-1].date, fmt='isodate')
        lst.extend([
            (', '.join('{} {}'.format(x.name, n_flagged(x)) for x in Flag),
             'Flags'),
            ('earliest {}, latest {}'.format(first, last), 'Range'),
            ])
    show(header, lst)


def show_entry(entry, verbose=0):
    """Show feed."""
    date_str = util.time_fmt(entry.date, fmt='isodate')
    header = [date_str, entry.feed.directory, entry.title]
    lst = []
    if verbose:
        lst.extend([
            # (util.time_fmt(entry.date_published, fmt='rfc2822'), 'Date'),
            (util.time_fmt(entry.date_published, fmt='isofull'), "Publ'd"),
            (util.time_fmt(entry.date_seen, fmt='isofull'), 'Seen'),
            (entry.score, 'Score'),
            (entry.flag.name, 'Flag'),
            (entry.guid, 'GUID'),
            (entry.link, 'Link'),
            (entry.title, 'Title'),
            (entry.subtitle, 'Subtitle'),
            (entry.summary, 'Summary'),
            (str(entry.get_tags()), 'Tags'),
            ])
        for enc in entry.encs():
            d = dict(href=enc.href, length=fmt_size(enc.length), typ=enc.typ,
                     name=enc.filename)
            try:
                d['size'] = fmt_size(enc.size())
                d['duration'] = util.fmt_duration(enc.duration())
                d['gain'] = media.fmt_gain(media.get_gain(enc.path))
            except FileNotFoundError:
                d['size'] = d['duration'] = d['gain'] = '-'
            s = '{size}, {duration}, {gain}, {name}'
            lst.append((s.format(**d), 'File'))
            s = '{length}, {typ}, {href}'
            lst.append((s.format(**d), 'File URL'))
    show(header, lst)


def show_files(entry, verbose=0):
    """Show files."""
    for enc in entry.encs():
        if verbose or enc.path.exists():
            print(shlex.quote(str(enc.path)))


def show_enclosure(enc):
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
    if enc.path.exists():
        log.debug('Already exists: %s', enc.path)
    elif enc.is_too_big(maxsize):
        log.warning('Download too big: %s: %s', fmt_size(enc.length), enc.path)
    else:
        # messager.msg(truncate('Downloading {}: {}'.format(
        #     fmt_size(enc.length), enc.path)))
        messager.msg('Downloading {}: {}'.format(fmt_size(enc.length),
                                                 enc.path), truncate=True)
        try:
            if not enc.download():
                log.error('Download failed: %s', enc.path)
        except NotImplementedError:
            log.debug('Download not implemented: %s', enc)
        except KeyboardInterrupt:
            log.error('Download interrupted: %s', enc)


def download_enclosures(entry, maxsize=None):
    """Download entry enclosures."""
    for enc in entry.encs():
        download_enclosure(enc, maxsize=maxsize)


def normalize_enclosure(enc, force=False):
    if enc.path.exists():
        if force or not enc.is_normalized():
            media.normalize_volume(enc.path)


def normalize_enclosures(entry, force=False):
    """Normalize loudness in enclosures."""
    for enc in entry.encs():
        normalize_enclosure(enc, force=force)


def play_enclosure(enc):
    try:
        if enc.path.exists():
            exit_code = enc.play()
        else:
            messager.msg('File does not exist: {}'.format(enc.path))
            messager.msg('Streaming: {}'.format(enc.href))
            exit_code = enc.stream()
        messager.msg('Exit code:', exit_code)
        return exit_code
    except NotImplementedError:
        log.error('Play/stream not implemented: %s', enc)
        return None


def play_enclosures(entry, set_flag=True):
    """Play entry enclosures."""
    exit_codes = (play_enclosure(x) for x in entry.encs())
    if set_flag and all(x == 0 for x in exit_codes):
        if entry.flag in [Flag.fresh, Flag.important, Flag.new]:
            messager.msg('Flagging entry as opened')
            entry.set_flag(Flag.opened)


def remove_enclosure(enc):
    """Remove enclosure from disk."""
    if enc.path.exists():
        messager.msg('Removing:', enc.path)
        enc.path.unlink()


def remove_enclosures(entry, set_flag=True):
    """Remove entry enclosures from disk."""
    for enc in entry.encs():
        remove_enclosure(enc)
    if set_flag:
        entry.set_flag('d')
