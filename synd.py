"""Syndicated feed with entries, based on feedparser library."""

import datetime
import logging
import re
import webbrowser
from contextlib import contextmanager
from functools import lru_cache
try:
    from http import HTTPStatus
except ImportError:
    from httpstatus import HTTPStatus  # HTTPStatus backported to 3.4.
from pathlib import Path
from statistics import mean

import common
import fpapi
import util
from entry import Entry
from misctypes import Flag, TagDict

log = logging.getLogger(__name__)
messager = util.Messager(__name__)


class Head():
    """Feed header."""
    def __init__(self, link, date_published, date_seen, author, title,
                 subtitle, summary, generator, language, publisher, rights,
                 image, tags):
        """Create new feed header."""
        self.link = link
        self.date_published = util.ParsedDatetime.parse(date_published)
        self.date_seen = util.ParsedDatetime.parse(date_seen)
        self.author = author
        self.title = title
        self.subtitle = subtitle
        self.summary = summary
        self.generator = generator
        self.language = language
        self.publisher = publisher
        self.rights = rights
        self.image = image
        self.tags = set(tags)

    def as_json(self):
        return dict(self.__dict__)

    @property
    def date(self):
        """Feed date."""
        return self.date_published or self.date_seen


class Feed():
    FEEDFILE = 'data.json'  # Feed information file.
    BAKEXT = '.bak'

    """Feed with entries."""
    def __init__(self, url, old_url=None, directory=None, parseinfo=None,
                 head=None, entries=None):
        """Create new feed."""
        self.url = url
        self.old_url = old_url
        self.directory = Path(directory) if directory else None
        self.parseinfo = parseinfo or {}
        self.head = Head(**head) if head else {}
        self.entries = [Entry(self, **x) for x in entries or []]
        self.modified = False
        self._nentries = None

    def __str__(self):
        return str(self.directory) or self.url

    def as_json(self):
        d = dict(
            url=self.url,
            old_url=self.old_url,
            directory=str(self.directory) if self.directory else None,
            parseinfo=self.parseinfo,
            head=self.head,
            entries=[x for x in self.entries],
            )
        return d

    def should_skip(self, gracetime=None):
        """Skip refresh or not? Gracetime given in hours."""
        tags = self.get_tags()
        if any(x in tags for x in 'inactive complete done'.split()):
            return True
        if 'gracetime' in tags:
            gracetime = float(tags['gracetime'])
        # if gracetime and self.head.date_seen and 'no_grace' not in tags:
        if gracetime and self.head.date_seen:
            delta = datetime.datetime.utcnow() - self.head.date_seen
            if delta.total_seconds() < gracetime * 60 * 60:
                return True
        return False

    def refresh(self, gracetime=None, force=False):
        """Retrieve and parse, if needed or forced. Return the number of
        updated entries, or None if feed skipped. Gracetime given in hours.
        """
        # TODO: Raise exceptions instead of return on error.
        if not force:
            if self.should_skip(gracetime):
                log.debug('Skipping refresh: %s', self)
                return None

        if force:
            etag, modified = None, None
        else:
            etag, modified = self.parseinfo['etag'], self.parseinfo['modified']
        fp = fpapi.parse(self.url, etag=etag, modified=modified)
        if 'status' not in fp:
            log.error('Error retrieving feed: %s: %s', self,
                      fp.bozo_exception)
            return 0
        try:
            status = HTTPStatus(fp.status)
        except ValueError as e:
            log.error('Error connecting: %s: %s', self, e)
            return 0
        if status == HTTPStatus.MOVED_PERMANENTLY:
            log.warning('Permanent redirect: %s moved from %s to %s', self,
                        self.url, fp.href)
            assert self.url != fp.href, self.url
            self.old_url, self.url = self.url, fp.href
            return self.refresh(force=True)

        elif status == HTTPStatus.NOT_MODIFIED:
            log.debug('Skipping refresh (not modified): %s', self)
            return None  # No need to download. Don't change anything.
        elif status == HTTPStatus.NOT_FOUND:
            log.error('Feed not found: %s: %s', self.directory, self.url)
            return None
        elif status == HTTPStatus.INTERNAL_SERVER_ERROR:
            log.warning('Internal server error: %s', self)
            return None
        elif status == HTTPStatus.UNAUTHORIZED:
            log.error('Feed password-protected: %s', self)
            return None
        elif status == HTTPStatus.GONE:
            log.warning('Feed gone, please stop polling: %s', self)
            return None

        elif status == HTTPStatus.FOUND:
            log.debug('Feed temporarily redirected: %s', self)
        elif status not in [HTTPStatus.OK]:
            log.warning('%s: Weird HTTP status: %s', self, status.name)
        try:
            return self.update(fp)
        except (KeyError, AttributeError) as e:
            log.error('Error parsing feed: %s: %s: %s', self, e, self.url)
            return 0

    def update(self, fp):
        """Update contents from a feedparser object. Return the number of
        updated entries.
        """
        log.debug('Updating feed: %s', self)
        self.parseinfo = fpapi.get_parseinfo(fp)
        self.head = Head(**(fpapi.get_head(fp.feed)))
        if not self.directory:
            self.directory = Path(self.head.title)
            log.warning('Got directory from title: %s', self.directory)
        entries = (Entry(**(fpapi.get_entry(x, self))) for x in fp.entries)
        n_updates = sum(self.add_entry(x) for x in entries)
        if n_updates:
            log.debug('Updated %i entries in feed: %s', n_updates, self)
            self.entries.sort()
        self.modified = True
        return n_updates

    def add_entry(self, entry):
        """Add another entry, if new or updated. Return True if changes done,
        False if not.
        """
        present = [x for x in self.entries if x.guid == entry.guid]
        assert len(present) < 2, len(present)
        if not present:
            # log.warning('Adding entry: %s: %s', self, entry)
            messager.msg(f'Adding entry: {self}: {entry}', truncate=True)
            # ##
            # import shutil
            # print('####', shutil.get_terminal_size().columns)
            # ##
            self.entries.append(entry)
            return True
        old = present[0]
        if entry.date_published and entry.date > old.date:
            # Replace old entry with new one, but keep flag info.
            # log.warning('Updating entry with newer: %s: %s: %s', self, entry,
            #             old.flag)
            s = 'Updating entry with newer: {}: {}: {}'
            messager.msg(s.format(self, entry, old.flag.name))
            entry.flag = old.flag
            self.entries.remove(old)
            self.entries.append(entry)
            return True
        if len(entry.enclosures) > len(old.enclosures):
            # However, if the entry got more enclosures, just replace all info.
            # Perhaps the publisher first forgot to add them.
            # log.warning('Updating entry with new enclosures: %s: %s: %s',
            #             self, entry, old.flag)
            s = 'Updating entry with new enclosures: {}: {}: {}'
            messager.msg(s.format(self, entry, old.flag.name))
            self.entries.remove(old)
            self.entries.append(entry)
            return True
        return False

    def customize_sortkey(self, sortkey):
        """Customize sortkey by tag contents."""
        if '=' not in sortkey:
            dateorder = self.get_tags().get('date')
            if dateorder == 'asc':
                sortkey = sortkey.replace('D', 'd')  # Ascending date.
            elif dateorder == 'desc':
                sortkey = sortkey.replace('d', 'D')  # Descending date.
            elif dateorder:
                log.error('Invalid date order: %s', self)
        return sortkey

    def list_entries(self, flags=None, sortkey=None, number=None):
        """List entries of certain criteria.

        Wildcards are '.' for any flag, -1 for infinite number.
        """
        entries = self.entries
        # if flags is not None and '.' not in flags:
        #     entries = [x for x in entries if x.flag in flags]
        if flags:
            flags = [Flag(x) for x in flags]
            entries = [x for x in entries if x.flag in flags]
        if sortkey is not None:
            sortkey = self.customize_sortkey(sortkey)
            sort_entries(entries, sortkey)
        self._nentries = len(entries)
        if number is not None and number != -1:
            entries = entries[:number]
        return entries

    def get_daystats(self, include_now=False, **kwargs):
        """Get stats on feed publishing frequency."""
        dates = sorted(x.date for x in self.list_entries(**kwargs))
        if include_now:
            dates.append(datetime.datetime.utcnow())
        if len(dates) < 3:
            raise ValueError(f'Not enough entries: {self}')
        deltas = [t2 - t1 for t1, t2 in zip(dates, dates[1:])]
        stats = util.timedelta_stats(deltas)
        daydeltas = map(util.timedelta_floatdays, deltas)
        daystats = map(util.timedelta_floatdays, stats.values())
        names = stats.keys()
        return list(daydeltas), tuple(daystats), tuple(names)

    def wait_to_refresh(self):
        """How much more should we wait until refresh?"""
        # TODO
        deltas, stats, names = self.get_daystats(include_now=False,
                                                 sortkey='D=', number=5)
        log.debug('%s %s %s', deltas, stats, names)
        return stats[0] / 2

    def check(self, verbose=False):
        """Feed sanity check."""
        status = HTTPStatus(self.parseinfo['status'])
        if status not in [HTTPStatus.OK, HTTPStatus.FOUND,
                          HTTPStatus.NOT_MODIFIED]:
            yield f'Weird HTTP status: {status.name}'
        if self.parseinfo['bozo']:
            yield f'Bozo: {self.parseinfo["bozo"]}'

        # if not self.head.subtitle:
        #     yield 'Empty subtitle'
        # if not self.head.summary:
        #     yield 'Empty summary'
        # if self.head.subtitle and self.head.subtitle == self.head.summary:
        #     yield 'Identical subtitle and summary'

        ##
        def len_(value):
            return -1 if value is None else len(value)

        yield 'Subtitle and summary: {} {} {}'.format(
            len_(self.head.subtitle), len_(self.head.summary),
            str(self.head.subtitle == self.head.summary)[0])
        ##

        tags = self.get_tags()
        for tag in tags:
            if not tags.is_sane(tag):
                yield f'Weird tag: {tag}'

        if not self.entries:
            yield 'No entries'
        if verbose:
            for e in self.entries:
                for msg in e.check():
                    yield msg
        orphans = self.get_orphans()
        if orphans:
            yield f'Orphan files: {len(orphans)}'

    def get_orphans(self):
        """Return list of orphaned files in feed directory."""
        dirfiles = {x.name for x in self.directory.iterdir()}
        p = Feed.data_path()
        datafiles = {str(p), str(p.with_suffix(p.suffix + self.BAKEXT))}
        encfiles = {enc.filename for entry in self.entries
                    for enc in entry.encs()}
        orphans = dirfiles.difference(datafiles).difference(encfiles)
        return sorted(orphans)

    def open_link(self):
        """Open feed link in web browser."""
        if self.head.link:
            webbrowser.open(self.head.link)

    @lru_cache()
    def get_tags(self):
        """Get feed tags."""
        tags = TagDict()
        for s in self.directory.parts:
            tags.parse(s)
        for s in self.head.tags:
            tags.parse(s)
        if self.head.language:
            if 'lang' in tags and tags['lang'] != self.head.language:
                log.debug('Overriding language tag %s with %s', tags['lang'],
                          self.head.language)
            tags['lang'] = self.head.language
        return tags

    @property
    @lru_cache()
    def priority(self):
        """Get feed priority (tag p=n). Greater number => greater interest."""
        try:
            return int(self.get_tags()['p'])
        except (KeyError, ValueError):
            return 0

    @classmethod
    def data_path(cls, directory=''):
        """Return feed data file path (relative)."""
        return Path(directory) / cls.FEEDFILE

    @property
    @lru_cache()
    def progress(self):
        if not self.entries:
            return 0
        return mean(x.progress for x in self.entries)

    @staticmethod
    def read(directory):
        """Read data."""
        d = common.read_data(Feed.data_path(directory))
        d['directory'] = directory
        feed = Feed(**d)
        return feed

    def write(self, directory=None, force=False):
        """Write data."""
        if self.modified or force:
            if directory is None:
                directory = self.directory
            common.write_data(Feed.data_path(directory), self)
            self.modified = False

    @classmethod
    @contextmanager
    def open(cls, directory):
        """Context manager for data file."""
        f = cls.read(directory)
        yield f
        f.write()


# TODO: Make a class of sortkey stuff, also with util.general_sort.
# TODO: Or a view.

SORTKEYS = {
    '=': lambda _: 0,  # Indicates no per-feed alterations allowed.
    'd': lambda entry: entry.date,
    'e': lambda entry: len(entry.enclosures),
    'f': lambda entry: entry.flag.index(),
    'i': lambda entry: str(entry.feed.directory).lower(),
    'l': lambda entry: (entry.feed.head.language or 'zzz').lower(),
    'n': lambda entry: entry.feed._nentries,
    'o': lambda entry: entry.feed.progress,
    'p': lambda entry: entry.feed.priority,
    'r': lambda entry: entry.progress,
    's': lambda entry: entry.score,
    't': lambda entry: entry.title.lower(),
    'u': lambda entry: entry.duration(),
    'x': lambda entry: entry.skipped(),
    'z': lambda entry: entry.size(),
    }


def sort_entries(entries, sortkey):
    """Sort entries by sortkey string."""
    keys = [SORTKEYS[x] for x in sortkey.lower()]
    reverses = [x.isupper() for x in sortkey]
    util.general_sort(entries, keys, reverses)


def search_entries(entries, patterns, flags=re.IGNORECASE, start=0):
    """Return index to first entry from start matching all RegExp patterns."""
    def get_strings(entry):
        """Return strings to match against."""
        return list(filter(None, [str(entry.feed.directory),
                                  entry.feed.head.title,
                                  entry.feed.head.subtitle,
                                  entry.feed.head.summary, entry.title,
                                  entry.subtitle, entry.summary]))

    def pattern_found(strings, pattern, flags):
        """Try matching."""
        # log.warning([strings, pattern])
        return any(re.search(pattern, x, flags=flags) for x in strings)

    for i, entry in enumerate(entries[start:], start):
        if all(pattern_found(get_strings(entry), x, flags) for x in patterns):
            return i
