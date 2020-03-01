"""Feedparser API."""

# TODO: Don't include microseconds in date_seen.

import datetime
import logging

import feedparser

log = logging.getLogger(__name__)


def get_now():
    """Get current time."""
    # return datetime.datetime.utcnow().replace(microseconds=0)
    return datetime.datetime.utcnow()


def get_title(fp):
    """Read title."""
    title = fp.title
    # assert title, (str(title), fp)
    assert title is not None, (str(title), fp)
    return title


def get_date(fp):
    """Read feed or entry publish date as datetime."""
    date = fp.get('published_parsed')
    if date is not None:
        date = datetime.datetime(*(date[:6]))  # The six are ymd hms.
    return date


def get_guid(fp):
    """Read entry GUID."""
    guid = fp.get('guid')
    if not guid:
        log.debug('Entry has no GUID, using enclosure URL instead: %s',
                  get_title(fp))
        guid = fp.enclosures[0]['href']
    if not guid:
        log.error('No entry GUID: %s', get_title(fp))
    assert guid, fp
    return guid


def get_parseinfo(fp):
    """Read parse info."""
    return dict(
        bozo=fp.get('bozo') and str(fp.get('bozo_exception')),
        encoding=fp.encoding,
        version=fp.get('version'),
        namespaces=fp.get('namespaces'),
        # Not using HTTPStatus here because YAML must output int.
        status=fp.get('status'),
        href=fp.get('href'),
        headers=fp.get('headers'),
        etag=fp.get('etag'),
        modified=fp.get('modified'),
        )


def get_head(fp):
    """Construct feed header."""
    return dict(
        link=fp.get('link'),
        date_published=get_date(fp),
        date_seen=get_now(),
        author=fp.get('author'),
        title=get_title(fp),
        subtitle=fp.get('subtitle'),
        summary=fp.get('summary'),
        generator=fp.get('generator'),
        language=fp.get('language'),
        publisher=fp.get('publisher'),
        rights=fp.get('rights'),
        image=fp.get('image', {}).get('href'),
        tags=[x.term for x in fp.get('tags', [])],
        )


def get_enclosure(fp):
    """Construct enclosure."""
    # Length must be converted from string to integer.
    # log.debug('Parsing enclosure: %s', fp.get('href'))
    try:
        # return dict(
        #     href=fp['href'],
        #     length=int(fp.get('length') or -1),
        #     type=fp['type'],
        #     )
        length = int(fp['length']) if fp.get('length', '').isdigit() else None
        return dict(
            href=fp['href'],
            length=length,
            type=fp.get('type'),
            )
    except Exception:
        log.error('Error parsing enclosure: %s', fp)
        raise


def get_entry(fp, feed):
    """Construct feed entry."""
    # log.debug('Parsing entry: %s', get_title(fp))
    try:
        return dict(
            feed=feed,
            guid=get_guid(fp),
            link=fp.get('link'),
            date_published=get_date(fp),
            date_seen=get_now(),
            author=fp.get('author'),
            title=get_title(fp),
            subtitle=fp.get('subtitle'),
            summary=fp.get('summary'),
            enclosures=[get_enclosure(x) for x in fp.get('enclosures', [])],
            tags=[x.term for x in fp.get('tags', [])],
            # flag='n',
            )
    except KeyError:
        log.error('Error parsing entry: %s', get_title(fp))
        raise


def parse(url, etag=None, modified=None):
    """Fetch and parse a feed file."""
    return feedparser.parse(url, etag=etag, modified=modified)
