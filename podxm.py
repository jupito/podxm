#!/usr/bin/python3

"""A podcast client."""

# FIXME: Don't use logging for normal output.

import logging
import shlex
from collections import defaultdict
from itertools import chain
from pathlib import Path

import common

from pyutils.files import tempfile_and_backup, valid_lines
from pyutils.misc import fmt_size, get_basic_parser, get_loglevel, get_progname

import synd

import ui_cmd

import util

log = logging.getLogger(get_progname())
messager = util.Messager(get_progname())
user_dirs = util.AppDirsPathlib(get_progname())


class Proc(object):
    """Program process state information."""
    def __init__(self, args):
        self.args = args
        session_path = user_dirs.user_cache_dir / 'session.json'
        self.session = common.TextDict(session_path)
        self.view = common.View(args)
        if args.view:
            self.view = self.view.parse(args.view)
        self.views = {}  # Optional feed-specific views.
        self.cache_feeds = False
        self.open_feeds = {}
        if args.recursive:
            self.view.directory = self.read_recursive_dirs(self.view.directory)

    @staticmethod
    def read_recursive_dirs(paths):
        """Search directory arguments recursively."""
        result = set()
        for path in paths:
            result.update(x.parent for x in path.rglob(synd.FEEDFILE))
        # log.warning([len(paths), len(result)])
        return sorted(result)

    def generate_feeds(self, view=None):
        """Generate feeds, optionally caching them."""
        if view is None:
            view = self.view
        for directory in view.directory:
            if self.cache_feeds:
                if directory not in self.open_feeds:
                    self.open_feeds[directory] = synd.Feed.read(directory)
                yield self.open_feeds[directory]
            else:
                with synd.Feed.open(directory) as feed:
                    yield feed

    def generate_entries(self, view=None):
        """Generate entries."""
        # if view is None:
        #     view = self.view
        # d = dict(flags=view.flags, sortkey=view.sortkey, number=view.number)
        for feed in self.generate_feeds(view=view):
            v = view or self.views.get(feed.directory) or self.view
            d = dict(flags=v.flags, sortkey=v.sortkey, number=v.number)
            log.debug('Using view: %s: %s', feed, d)
            for entry in feed.list_entries(**d):
                yield entry

    def clear_cache(self):
        """Clear feed cache."""
        self.open_feeds = {}

    def add_urls(self, urls):
        """Add feeds from URLs."""
        for url in urls:
            if self.args.verbose:
                messager.msg('Adding: {}'.format(url))
            directory = common.add_url(url)
            messager.msg('Created: {}'.format(directory))

    def cmd_add(self):
        """Add feeds from URLs."""
        urls = chain(self.args.url or [],
                     chain(valid_lines(x) for x in self.args.urllist or []))
        self.add_urls(urls)

    def cmd_refresh(self):
        """Refresh feeds. Using --force forces retrieval."""
        n_skipped = 0
        n_new_entries = 0
        for feed in self.generate_feeds():
            r = feed.refresh(gracetime=self.args.gracetime,
                             force=self.args.force)
            if r is None:
                n_skipped += 1
            else:
                n_new_entries += r
        s = 'Found {} new entries in {} feeds, skipped {} feeds'
        messager.msg(s.format(n_new_entries,
                              len(self.view.directory)-n_skipped, n_skipped))

    def cmd_check(self, path=None):
        """Check feeds. Write list of orphaned files. Using --force forces
        configuration rewrite.
        """
        if path is None:
            path = user_dirs.user_cache_dir / 'orphans.txt'
        orphans = []
        for feed in self.generate_feeds():
            seq = common.check_feed(feed)
            seq = (feed.directory / x for x in seq)
            orphans.extend(seq)
            if self.args.force:
                feed.modified = True  # Force configuration rewrite.
        if orphans:
            write_pathlist(orphans, path)

    def cmd_dl(self):
        """Download enclosures. Using --force forces download even against feed
        settings.
        """
        # First read any feed-specific settings.
        if not self.args.force:
            for feed in self.generate_feeds():
                s = feed.get_tags().get('dl')
                if s:
                    view = self.view.parse(',,{}'.format(s))
                    self.views[feed.directory] = view
        for entry in self.generate_entries():
            common.download_enclosures(entry, self.args.maxsize)

    def cmd_norm(self):
        """Normalize enclosure loudness. Using --force re-normalizes."""
        for entry in self.generate_entries():
            common.normalize_enclosures(entry, self.args.force)

    def cmd_setflag(self):
        """Set flag for entries to --new_flag value."""
        for entry in self.generate_entries():
            if self.args.verbose:
                messager.msg(entry.feed, entry.title)
            entry.set_flag(self.args.new_flag)

    def cmd_show_feed(self):
        """Show feeds."""
        for feed in self.generate_feeds():
            common.show_feed(feed, verbose=self.args.verbose)

    def cmd_show_entry(self):
        """Show entries."""
        for entry in self.generate_entries():
            common.show_entry(entry, verbose=self.args.verbose)

    def cmd_show_files(self):
        """Show entries."""
        for entry in self.generate_entries():
            common.show_files(entry, verbose=self.args.verbose)

    def cmd_show_tags(self):
        """Show tags for feeds or entries."""
        tag_count = defaultdict(int)
        if self.args.verbose:
            # Consider tags of (filtered) entries.
            for entry in self.generate_entries():
                for tag in entry.get_tags().as_strings():
                    tag_count[tag] += 1
        else:
            # Consider feed tags only.
            for feed in self.generate_feeds():
                for tag in feed.get_tags().as_strings():
                    tag_count[tag] += 1
        for tag, cnt in sorted(tag_count.items()):
            messager.msg('{cnt:7} {tag}'.format(cnt=cnt, tag=tag))

    def cmd_show_dates(self):
        """Show stats about publish date deltas, or deltas themselves
        (verbose).
        """
        d = dict(flags=self.args.flags, sortkey=self.args.sortkey,
                 number=self.args.number)
        names = None
        for feed in self.generate_feeds():
            try:
                deltas, stats, names = feed.get_daystats(include_now=True, **d)
            except ValueError:
                log.warning('Daystats not available for feed "%s"', feed)
            else:
                values = sorted(deltas) if self.args.verbose else stats
                lst = ['{: >7.1f}'.format(x) for x in values] + [feed]
                messager.msg(*lst)
            # log.info('%.2f %s', feed.wait_to_refresh(), feed)
        if not self.args.verbose and names is not None:
            messager.msg(*names)

    def cmd_show_cal(self):
        """Show calendar view of entries."""
        months = {}
        days = {}
        for entry in self.generate_entries():
            d = entry.date
            months.setdefault((d.year, d.month), []).append(entry)
            days.setdefault((d.year, d.month, d.day), []).append(entry)
        for k, v in sorted(months.items())[-2:]:
            messager.msg()
            messager.msg('#### {} ####'.format(k))
            messager.msg()
            for entry in sorted(v):
                common.show_entry(entry, verbose=self.args.verbose)
        for k, v in sorted(days.items())[-2:]:
            messager.msg()
            messager.msg('#### {} ####'.format(k))
            messager.msg()
            for entry in sorted(v):
                common.show_entry(entry, verbose=self.args.verbose)

    def cmd_ui(self):
        """Run UI."""
        ui = ui_cmd.UI(self)
        ui.run(jump=True)

    @classmethod
    def cmds(cls):
        return {x.split('_', 1)[1]: x for x in dir(cls) if
                x.startswith('cmd_')}

    def run_cmd(self, cmd):
        """Run command."""
        name = self.cmds()[cmd]
        f = getattr(self, name)
        f()


def get_config_paths():
    """Return default configuration files."""
    filename = '{}.cfg'.format(get_progname())
    paths = [user_dirs.user_config_dir / filename, Path(filename)]
    paths = (x for x in paths if x.exists())
    return paths


def parse_config(parser):
    """Parse configuration files."""
    prefix = parser.fromfile_prefix_chars[0]
    args = ['{}{}'.format(prefix, x) for x in get_config_paths()]
    namespace = parser.parse_args(args)
    return namespace


def write_pathlist(paths, path):
    """Write path list."""
    s = 'Writing list of {} orphan files to {}'
    messager.msg(s.format(len(paths), path))
    lines = ('{} {}'.format(fmt_size(x.stat().st_size), shlex.quote(str(x)))
             for x in paths)
    with tempfile_and_backup(path, 'w') as f:
        for line in lines:
            # If formatting needed, this seems fastest: '%s\n' % line
            f.write(line + '\n')


def parse_args():
    """Parse arguments."""
    epilog = 'Long options can be abbreviated unambigously'
    parser = get_basic_parser(description=__doc__, epilog=epilog)
    parser.add('-c', '--commands', nargs='+', choices=Proc.cmds().keys(),
               help='commands')
    parser.add('-d', '--directory', nargs='+', type=Path,
               help='directories')
    parser.add('-r', '--recursive', action='store_true', default=True,
               help='recurse directories')
    parser.add('-f', '--flags',
               help='flag filter for entries')
    parser.add('-s', '--sortkey',
               help='entry sort key')
    parser.add('-S', '--sortkey2',
               help='entry sort key 2')
    parser.add('-n', '--number', type=int,
               help='maximum number of entries to process')
    parser.add('-w', '--view',
               help='view (f,s,n,S)')
    parser.add('-u', '--url', nargs='*',
               help='URLs to add')
    parser.add('-U', '--urllist', nargs='*',
               help='list file of URLs to add')
    parser.add('--new_flag', choices=[x.value for x in synd.Flag],
               help='new flag value for setflag command')
    parser.add('--gracetime', type=float, default=5,
               help='refresh grace time in hours')
    parser.add('--maxsize', type=float, default=300,
               help='maximum download size (MB)')
    parser.add('--force', action='store_true',
               help='force operation (depends on command)')
    namespace = parse_config(parser)
    return parser.parse_args(namespace=namespace)


def main():
    """Main."""
    args = parse_args()
    logging.basicConfig(filename=args.logfile,
                        level=get_loglevel(args.loglevel))
    args = util.AttrDict(args.__dict__)
    proc = Proc(args)
    for cmd in args.commands:
        proc.run_cmd(cmd)


if __name__ == '__main__':
    main()
