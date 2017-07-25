"""Feed entry."""

import logging
from functools import lru_cache, total_ordering

import media
import util
from enclosure import Enclosure, YleEnclosure, YoutubeEnclosure
from misctypes import Flag, TagDict

log = logging.getLogger(__name__)
messager = util.Messager(__name__)


@total_ordering
class Entry(object):
    """Feed entry."""
    def __init__(self, feed, guid, link, date_published, date_seen, author,
                 title, subtitle, summary, enclosures, tags, flag='n'):
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
        # self.progress = progress  # TODO

    def __str__(self):
        return self.title or self.link or self.guid

    def __lt__(self, other):
        return self.date < other.date

    def as_json(self):
        d = dict(self.__dict__)
        del d['feed']
        return d

    @property
    def date(self):
        """Return entry date."""
        return self.date_published or self.date_seen

    @property
    def abbreviated_title(self, ellipsis='…'):
        """Abbreviate title (remove possible duplication of feed title)."""
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

    def check(self):
        """Entry sanity check."""
        # TODO: Check for duplicate enclosures.
        if self.date > self.feed.head.date_seen:
            s = ('{e}: Entry claims to be newer than feed: {e.date}' +
                 ' > {e.feed.head.date_seen}')
            yield s.format(e=self)
        n = len(self.enclosures)
        if n > 1:
            s = '{e}: Multiple enclosures: {n}'
            yield s.format(e=self, n=n)
        # if self.flag in [Flag.important, Flag.archived]:
        #     for enc in self.encs():
        #         if not enc.path.exists():
        #             yield '{e}: Missing file: {p}'.format(e=self, p=enc.path)
        for enc in self.encs():
            if not enc.suffix:
                yield '{e}: No file suffix'.format(e=self)
            if self.flag in [Flag.important, Flag.archived]:
                if not enc.path.exists():
                    yield '{e}: Missing file: {p}'.format(e=self, p=enc.path)

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
        media.open_link(self.link)
