"""Enclosure classes."""

from functools import lru_cache
import logging

import pyutils.misc
import pyutils.files

import media
import util

log = logging.getLogger(__name__)


class Enclosure(object):
    """Feed entry enclosure."""
    def __init__(self, entry, href, length, typ):
        """Create new enclosure."""
        self.entry = entry  # Parent entry.
        self.href = href  # Media URL.
        self.length = length  # XXX: Update when known?
        self.typ = typ  # XXX: Remove?

    def __str__(self):
        return self.href

    @property
    @lru_cache()
    def suffix(self):
        """URL filename suffix."""
        suffix = pyutils.misc.url_suffix(self.href)
        if not suffix:
            if self.typ:
                parts = self.typ.split('/')
                suffix = '.' + parts[-1]
            else:
                suffix = '.unknown'
        return suffix

    @property
    @lru_cache()
    def filename(self):
        """Filename on disk."""
        date_str = util.time_fmt(self.entry.date, fmt='isodate')
        title = self.entry.title[:80]
        name = '{d}_{t}{e}'.format(d=date_str, t=title, e=self.suffix)
        name = name.replace('/', '%')
        return name

    @property
    @lru_cache()
    def path(self):
        """Path on disk."""
        return self.entry.feed.directory / self.filename

    def size(self):
        """Size on disk."""
        return self.path.stat().st_size

    def is_too_big(self, maxsize):
        """Is it too big to download? Maximum size is given in megabytes."""
        return maxsize is not None and (self.length or 0) > maxsize * 1024**2

    def duration(self):
        """Media duration."""
        return media.get_duration(self.path)

    def is_normalized(self):
        """Has loudness been normalized?"""
        return media.get_gain(self.path) is not None

    def download(self):
        """Download file."""
        # log.info('Downloading: %s', self.path)
        pyutils.files.ensure_dir(self.path)
        return pyutils.misc.download(self.href, self.path, progress=True)

    def play(self):
        """Play downloaded file."""
        return media.play_file(self.path)

    def stream(self):
        """Stream from net."""
        return media.play_stream(self.href)

    def remove(self):
        """Remove from disk."""
        if self.path.exists():
            self.path.unlink()
        for path in self.path.parent.glob('{}.*.srt'.format(self.path.stem)):
            logging.warning('Removing subtitle: %s', path)


class YleEnclosure(Enclosure):
    """Yle media. No streaming support."""
    def __init__(self, entry):
        super().__init__(entry, entry.link, None, None)

    @property
    def suffix(self):
        return '.flv'

    def download(self):
        pyutils.files.ensure_dir(self.path)
        return media.download_yle(self.href, self.path)

    def stream(self):
        raise NotImplementedError()


class YoutubeEnclosure(Enclosure):
    """Youtube media. Support only streaming for now."""
    def __init__(self, entry):
        super().__init__(entry, entry.link, None, None)

    @property
    def suffix(self):
        return '.flv'

    def download(self):
        raise NotImplementedError()

    def play(self):
        raise NotImplementedError()