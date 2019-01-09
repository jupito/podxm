"""Feed entry."""

import logging
import webbrowser
from functools import lru_cache, total_ordering

from pyutils.misc import int_or_float

import util
from enclosure import Enclosure, YleEnclosure, YoutubeEnclosure
from misctypes import Flag, TagDict

log = logging.getLogger(__name__)
messager = util.Messager(__name__)


@total_ordering
class Entry():
    """Feed entry."""
    def __init__(self, feed, guid, link, date_published, date_seen, author,
                 title, subtitle, summary, enclosures, tags, flag=Flag.fresh,
                 progress=0):
        """Create new entry."""
        self.feed = feed  # Parent feed object.
        self.guid = guid
        self.link = link
        self.date_published = util.ParsedDatetime.parse(date_published)
        self.date_seen = util.ParsedDatetime.parse(date_seen)
        self.author = author
        self.title = title
        self.subtitle = subtitle
        self.summary = summary
        self.enclosures = enclosures
        self.tags = tags
        self.flag = Flag(flag)
        self.progress = progress

    def __str__(self):
        return self.title or self.link or self.guid

    def __lt__(self, other):
        return self.date < other.date

    def as_json(self):
        d = dict(self.__dict__)
        del d['feed']
        d['progress'] = d.pop('_progress')
        return d

    @property
    def date(self):
        """Return entry date."""
        return self.date_published or self.date_seen

    @property
    def abbreviated_title(self):
        """Abbreviate title (remove possible duplication of feed title)."""
        ellipsis = '…'
        title = self.title
        if self.feed.head and self.feed.head.title:
            title = title.replace(self.feed.head.title + ': ', ellipsis)
            title = title.replace(self.feed.head.title, ellipsis)
        return title

    @property
    def score(self):
        """Get entry score. Greater number => greater interest."""
        return self.feed.priority + self.flag.score()

    @lru_cache()
    def get_tags(self):
        """Get entry tags (including feed tags)."""
        tags = TagDict()
        for s in self.tags:
            tags.parse(s)
        tags.update(self.feed.get_tags())  # Feed tags override entry tags.
        return tags

    def set_flag(self, value):
        """Set flag."""
        flag = Flag(value)
        if self.flag != flag:
            self.flag = flag
            self.feed.modified = True

    @property
    def status(self):
        # TODO: Replace 'flag' with 'status'; use properties.
        return self.flag

    @status.setter
    def status(self, value):
        # TODO: Replace 'flag' with 'status'; use properties.
        self.set_flag(value)

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = int_or_float(value)
        self.feed.modified = True

    def skipped(self):
        """Was entry skipped without listening?"""
        return self.status == Flag.deleted and self.progress == 0

    def check(self):
        """Entry sanity check."""
        encs = list(self.encs())
        d = dict(e=self, n=len(encs))

        if self.date > self.feed.head.date_seen:
            yield ('{e}: Entry claims to be newer than feed: {e.date}' +
                   ' > {e.feed.head.date_seen}').format(**d)

        # if not self.subtitle:
        #     yield '{e}: Empty subtitle'.format(**d)
        # if not self.summary:
        #     yield '{e}: Empty summary'.format(**d)
        # if self.subtitle and self.subtitle == self.summary:
        #     yield '{e}: Identical subtitle and summary'.format(**d)

        ##
        def len_(value):
            return -1 if value is None else len(value)

        yield 'Subtitle and summary: {} {} {}'.format(
            len_(self.subtitle), len_(self.summary),
            str(self.subtitle == self.summary)[0])
        ##

        if d['n'] > 1:
            yield '{e}: Multiple enclosures: {n}'.format(**d)
        if self.flag == Flag.deleted and 'archived' in self.get_tags():
            yield '{e}: Deleted entry in archived feed.'.format(**d)
        for i, enc in enumerate(encs):
            d.update(i=i, p=enc.path, u=enc.href)
            if not enc.suffix:
                yield '{e} #{i}: No file suffix: {p}'.format(**d)
            if any(x.href == enc.href for x in encs[:i]):
                yield '{e} #{i}: Duplicate link: {u}'.format(**d)
            if self.flag in [Flag.important, Flag.archived]:
                if not enc.path.exists():
                    yield '{e} #{i}: Missing file: {p}'.format(**d)

    def encs(self):
        """Generate (enclosure, dst_path, exists) tuples for entry."""
        if self.enclosures:
            for e in self.enclosures:
                yield Enclosure(self, e['href'], e['length'], e['type'])
        elif (self.link.startswith('http://areena.yle.fi/') or
              self.link.startswith('https://areena.yle.fi/')):
            yield YleEnclosure(self)
        elif (self.link.startswith('http://www.youtube.com/') or
              self.link.startswith('https://www.youtube.com/')):
            yield YoutubeEnclosure(self)

    @property
    @lru_cache()
    def enc(self):
        """Shorcut."""
        lst = list(self.encs())
        if lst:
            return lst[0]
        else:
            raise FileNotFoundError('No enclosures: {}'.format(self))

    def duration(self):
        return sum((x.duration() or 0) for x in self.enclosures)

    def size(self):
        return sum((x.size() or 0) for x in self.enclosures)

    def open_link(self):
        """Open entry link in web browser."""
        if self.link:
            webbrowser.open(self.link)
