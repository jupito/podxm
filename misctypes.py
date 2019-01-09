"""Misc types."""

import logging
from enum import Enum, unique
from functools import total_ordering

import attr
from attr.validators import in_, instance_of, optional

log = logging.getLogger(__name__)


@total_ordering
@unique
class Flag(Enum):
    """Feed entry status flag."""
    # https://docs.python.org/3/library/enum.html
    fresh = 'f'
    opened = 'o'
    important = 'i'
    new = 'n'
    archived = 'a'
    deleted = 'd'

    # def __str__(self):
    #     return self.name

    def __lt__(self, other):
        """Comparison is useful for sorting in user interface."""
        lst = list(self.__class__)
        return lst.index(self) < lst.index(other)

    def index(self):
        """Flag index."""
        return list(self.__class__).index(self)

    def score(self):
        """Score associated with flag."""
        return (self.index() - 3) * -100

    def as_json(self):
        """Represent as JSON (one-way conversion)."""
        return self.value


class TagDict(dict):
    """Collection of tags."""
    def parse(self, s):
        """Parse tags from string."""
        self.update(TagDict.split_tag(x) for x in s.split(','))

    def as_strings(self):
        """Represent as strings."""
        def as_str(k, v):
            """Represent as string."""
            return '='.join(filter(None, [k, v]))
        return (as_str(k, v) for k, v in self.items())

    def __str__(self):
        return ','.join(sorted(self.as_strings()))

    @staticmethod
    def split_tag(tag, sep='=', default=None):
        """Split tag string into key and value. Return None on error."""
        try:
            k, v = tag.split(sep, 2)
        except ValueError:
            k, v = tag, default
        k = TagDict.normalize_tag(k)
        return k, v

    @staticmethod
    def normalize_tag(tag, space='_'):
        """Normalize tag."""
        return tag.strip().lower().replace(' ', space).replace("'", '')

    @staticmethod
    def is_sane(k):
        """Is tag well-behaving?"""
        return len(k) and all(x.isalnum() or x in '_&/-:' for x in k)


@attr.s(frozen=True)
class Gain():
    """ReplayGain level."""
    value = attr.ib(validator=instance_of(float), convert=float)
    unit = attr.ib(default='LU', validator=in_(['LU', 'dB']))

    def __str__(self):
        return f'{self.value}{self.unit}'

    @classmethod
    def parse(cls, s):
        return cls(*s.split())

    def _asdict(self):
        return attr.asdict(self)


@attr.s(frozen=True)
class Lang():
    """Language (and maybe country) code."""
    lang = attr.ib(validator=instance_of(str))
    country = attr.ib(default=None, validator=optional(instance_of(str)))

    def __attrs_post_init__(self):
        assert all(len(x) == 2 for x in filter(None, [self.lang,
                                                      self.country])), self

    def __str__(self):
        return '_'.join(filter(None, [self.lang, self.country]))

    @classmethod
    def parse(cls, s):
        return cls(*s.split('_'))
