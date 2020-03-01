#!/usr/bin/python3

"""A podcast client."""

# FIXME: Don't use logging for normal output.

import logging
from collections import defaultdict
from itertools import chain
from pathlib import Path

from jupitotools.args import get_basic_parser
from jupitotools.files import tempfile_and_backup, valid_lines
from jupitotools.misc import get_loglevel, get_progname

import common
import ui_cmd
import util
from misctypes import Flag
from synd import Feed

log = logging.getLogger(get_progname())
messager = util.Messager(get_progname())
user_dirs = util.AppDirsPathlib(get_progname())


class Proc():
    """Program process state information."""
    session_path = user_dirs.user_cache_dir / 'session.json'
    orphans_path = user_dirs.user_cache_dir / 'orphans.txt'

    def __init__(self, args):
        self.args = args
        self.session = common.TextDict(self.session_path)
        # TODO: Use only --view.
        self.view = common.View(directory=args.directory, flags=args.flags,
                                number=args.number, sortkey=args.sortkey,
                                sortkey2=args.sortkey2)
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
            result.update(x.parent for x in path.rglob(Feed.FEEDFILE))
        # log.warning([len(paths), len(result)])
        return sorted(result)

    def generate_feeds(self, view=None):
        """Generate feeds, optionally caching them."""
        if view is None:
            view = self.view
        for directory in view.directory:
            if self.cache_feeds:
                if directory not in self.open_feeds:
                    self.open_feeds[directory] = Feed.read(directory)
                yield self.open_feeds[directory]
            else:
                with Feed.open(directory) as feed:
                    yield feed

    def generate_entries(self, view=None):
        """Generate entries."""
        # if view is None:
        #     view = self.view
        # d = dict(flags=view.flags, number=view.number, sortkey=view.sortkey)
        for feed in self.generate_feeds(view=view):
            v = view or self.views.get(feed.directory) or self.view
            d = dict(flags=v.flags, number=v.number, sortkey=v.sortkey)
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
                messager.msg(f'Adding: {url}')
            directory = common.add_url(url)
            messager.msg(f'Created: {directory}')

    def cmd_add(self):
        """Add feeds from URLs."""
        file_urls = chain(valid_lines(x) for x in self.args.urllist or [])
        urls = chain(self.args.url or [], file_urls)
        self.add_urls(urls)

    def cmd_refresh(self):
        """Refresh feeds. Using --force forces retrieval."""
        n_skipped = 0
        n_new = 0
        for feed in self.generate_feeds():
            r = feed.refresh(gracetime=self.args.gracetime,
                             force=self.args.force)
            if r is None:
                n_skipped += 1
            else:
                n_new += r
        if self.args.verbose:
            s = 'Found {} new entries in {} feeds, skipped {} feeds'
            messager.msg(s.format(n_new, len(self.view.directory) - n_skipped,
                                  n_skipped))

    def cmd_check(self, path=None):
        """Check feeds. Write list of orphaned files. Using --force forces
        configuration rewrite.
        """
        if path is None:
            path = self.orphans_path
        orphans = []
        for feed in self.generate_feeds():
            seq = common.check_feed(feed, verbose=self.args.verbose)
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
                    view = self.view.parse(f',{s},,')
                    self.views[feed.directory] = view
                    # print(feed, self.views[feed.directory])
        for entry in self.generate_entries():
            common.download_enclosures(entry, self.args.maxsize)

    def cmd_norm(self):
        """Normalize enclosure loudness. Using --force re-normalizes."""
        for entry in self.generate_entries():
            common.normalize_enclosures(entry, force=False)

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
            messager.msg(f'{cnt:7} {tag}')

    def cmd_show_dates(self):
        """Show stats about publish date deltas, or deltas themselves
        (verbose).
        """
        # TODO: Use only --view.
        d = dict(flags=self.args.flags, number=self.args.number,
                 sortkey=self.args.sortkey)
        names = None
        for feed in self.generate_feeds():
            try:
                deltas, stats, names = feed.get_daystats(include_now=True, **d)
            except ValueError:
                log.warning('Daystats not available for feed "%s"', feed)
            else:
                values = sorted(deltas) if self.args.verbose else stats
                lst = ['f{x: >7.1f}' for x in values] + [feed]
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
            messager.msg(f'#### {k} ####')
            messager.msg()
            for entry in sorted(v):
                common.show_entry(entry, verbose=self.args.verbose)
        for k, v in sorted(days.items())[-2:]:
            messager.msg()
            messager.msg(f'#### {k} ####')
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
    dirnames = [user_dirs.user_config_dir, '.']
    filename = f'{get_progname()}.cfg'
    paths = [Path(x) / filename for x in dirnames]
    return [x for x in paths if x.exists()]


def parse_config(parser):
    """Parse configuration files."""
    prefix = parser.fromfile_prefix_chars[0]
    args = [f'{prefix}{x}' for x in get_config_paths()]
    return parser.parse_args(args)


def write_pathlist(paths, path):
    """Write path list."""
    messager.msg(f'Writing list of {len(paths)} orphan files to {path}')
    lines = (str(x) for x in paths)
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
    parser.add('-w', '--view',
               help='view (f,n,s,S)')
    parser.add('-u', '--url', nargs='*',
               help='URLs to add')
    parser.add('-U', '--urllist', nargs='*',
               help='list file of URLs to add')
    parser.add('--new_flag', choices=[x.value for x in Flag],
               help='new flag value for setflag command')
    parser.add('--gracetime', type=float, default=5,
               help='refresh grace time in hours')
    parser.add('--maxsize', type=float, default=350,
               help='maximum download size (MB)')
    parser.add('--force', action='store_true',
               help='force operation (depends on command)')

    # TODO: The rest are obsolete.
    parser.add('--flags',
               help='flag filter for entries')
    parser.add('--number', type=int,
               help='maximum number of entries to process')
    parser.add('--sortkey',
               help='entry sort key')
    parser.add('--sortkey2',
               help='entry sort key 2')
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
