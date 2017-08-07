"""Line-oriented UI."""

# https://docs.python.org/3.6/library/cmd.html

import cmd
import logging
import shlex

import common
from common import View

import pyutils.misc

import synd
from synd import Flag

import util

log = logging.getLogger(__name__)
messager = util.Messager(__name__)
# message = common.message
# feedback = common.feedback


class UI(cmd.Cmd):
    """Show entries interactively."""
    intro = 'Welcome'
    separator = ';'  # Separator for multiple commands on one line.

    def __init__(self, proc, view=None):
        super().__init__()
        self.proc = proc
        self.entries = None
        self._i = 0
        self.lastcmd = 'n'
        self.lastline = self.lastcmd
        self.n_cmds = 0  # Number of commands given, if several.
        self.view = View(**proc.view)
        if view is not None:
            self.view.update(view)
        self.proc.cache_feeds = True
        self.read_data()

    def __del__(self):
        # super().__del__()  # Doesn't have one.
        # d = dict(directory=self.view.directory, entry=None, feed=None)
        d = dict(entry=None, feed=None)
        d['directory'] = [str(x) for x in self.view.directory]
        if self.entries:
            d.update(entry=self.entry.guid, feed=self.feed.url)
        self.proc.session.update(d)
        self.proc.session.write()
        self.write_data()

    def read_data(self, force=False):
        """Read data."""
        # s = 'Reading with f={flags}, s={sortkey}, n={number}, S={sortkey2}'
        # message(s.format(**self.view))
        messager.msg('Reading with {}'.format(self.view))
        if force:
            self.proc.clear_cache()
        entries = list(self.proc.generate_entries(view=self.view))
        synd.sort_entries(entries, self.view.sortkey2)
        self.entries = entries

    def write_data(self, force=False):
        """Write data."""
        feeds = self.proc.open_feeds.values()
        messager.msg('Writing {} feeds'.format(len(feeds)))
        for feed in feeds:
            feed.write(force=force)

    def run(self, jump=False, guid=None, url=None):
        """Run user interaction loop."""
        if jump:
            guid = guid or self.proc.session.get('entry')
            url = url or self.proc.session.get('feed')
            if guid is not None or url is not None:
                self.jump(guid, url)
        if self.entries:
            self.cmdloop()
        else:
            messager.msg('There are no entries. Bye!')

    def jump(self, guid=None, url=None):
        """Jump to entry or feed."""
        index = None
        for i, e in enumerate(self.entries):
            if guid is not None and e.guid == guid:
                index = i
                msg = 'Jumping to entry...'
                break
            if index is None and url is not None and e.feed.url == url:
                index = i
                msg = 'Jumping to feed...'
        if index is None:
            msg = 'Cannot find jump destination.'
        else:
            self.i = index
        messager.msg(msg)

    @property
    def i(self):
        return self._i

    @i.setter
    def i(self, value):
        self._i = pyutils.misc.clamp(value, 0, len(self.entries) - 1)

    @property
    def entry(self):
        """Current entry."""
        return self.entries[self.i]

    @property
    def feed(self):
        """Feed of current entry."""
        return self.entry.feed

    def get_row(self, i=None):
        """Get a line of info for the prompt or line selector."""
        if i is None:
            i = self.i
        entry = self.entries[i]
        d = dict(
            i=i,
            n=len(self.entries),
            nfe=entry.feed._nentries or -1,
            flag=entry.flag.value,
            dir=entry.feed.directory,
            d=util.time_fmt(entry.date, fmt='compactdate'),
            dl=sum(x.path.exists() for x in entry.encs()),
            nl=sum(x.is_normalized() for x in entry.encs()),
            t=entry.abbreviated_title,
            )
        s = '{flag}{dl}{nl} {i:2d}/{n:2d} {nfe:2d} {d} {dir}●{t}'
        return s.format(**d)

    def get_prompt(self):
        """Get command prompt string. Long entry titles are shortened."""
        s = '{{x}} [{default}] '.format(default=self.lastline)
        return s.format(x=pyutils.misc.truncate(self.get_row(),
                                                reserved=len(s)))

    @property
    def prompt(self):
        return self.get_prompt()

    # def preloop(self):
    #     print('preloop')

    # def postloop(self):
    #     print('postloop')

    def precmd(self, line):
        # print('precmd "{}"'.format(line), self.lastline, self.n_cmds)
        if not line:
            line = self.lastline
        lines = line.split(self.separator)
        if len(lines) > 1:
            self.lastline = line
            self.n_cmds = len(lines)  # Commands given.
        first = lines.pop(0)
        self.cmdqueue.extend(lines)
        return first

    def postcmd(self, stop, line):
        # print('postcmd "{}"'.format(line), self.lastline, self.n_cmds)
        if self.n_cmds:
            self.n_cmds -= 1  # Processing multicommand.
        elif line:
            self.lastline = line  # Processing single command.
        if not self.entries:
            messager.msg('There are no entries. Bye!')
            return True
        return stop

    def do_EOF(self, arg):
        """Quit."""
        return True

    def do_next(self, arg):
        """Move to next item in list."""
        delta = int(arg or 1)
        self.i += delta

    def do_back(self, arg):
        """Move to previous item in list."""
        delta = int(arg or 1)
        self.i -= delta

    def do_go(self, arg):
        """Go to indexed item."""
        if arg == 'G':
            self.i = len(self.entries) - 1
        else:
            self.i = int(arg or 0)

    def do_list(self, arg):
        # lines = ('{e.feed}: {e}'.format(e=x) for x in self.entries)
        lines = (self.get_row(i) for i in range(len(self.entries)))
        out = pyutils.misc.peco(lines, initial=self.i, index=True)
        if out is not None:
            self.do_go(out[0])

    def do_nextfeed(self, arg):
        """Skip to next feed."""
        cnt = 0
        next_feed = self.feed
        while self.i+cnt < len(self.entries)-1 and next_feed == self.feed:
            cnt += 1
            next_feed = self.entries[self.i+cnt].feed
        if next_feed != self.feed:
            self.i += cnt

    def do_search(self, arg):
        """Search entries."""
        patterns = shlex.split(arg) or self.proc.session.get('search_patterns')
        if patterns:
            i = synd.search_entries(self.entries, patterns, start=self.i+1)
            if i is None:
                messager.feedback('Not found: {}'.format(patterns))
            else:
                self.i = i
            self.proc.session['search_patterns'] = patterns

    def do_view(self, arg):
        """Show info on entry."""
        targets = arg or 'e'
        if 'f' in targets:
            common.show_feed(self.feed, verbose=2)
        if 'e' in targets:
            common.show_entry(self.entry, verbose=2)
            if self.entry.flag == Flag.fresh:
                messager.feedback('Flagging fresh entry as new.')
                self.entry.set_flag(Flag.new)
        if 'm' in targets:
            common.show_enclosures(self.entry)
        if 'fl' in targets:
            self.feed.open_link()
        if 'el' in targets:
            self.entry.open_link()

    def do_download(self, arg):
        """Download enclosures."""
        try:
            if self.entry.flag == Flag.deleted:
                messager.feedback('Flagging deleted entry as new.')
                self.entry.set_flag(Flag.new)
                self.feed.write()
            maxsize = int(arg or self.proc.args.maxsize)
            common.download_enclosures(self.entry, maxsize=maxsize)
        except ValueError as e:
            messager.feedback(e)

    def do_normalize(self, arg):
        """Normalize volume."""
        force = bool(int(arg or 0))
        common.normalize_enclosures(self.entry, force=force)

    def do_play(self, arg):
        """Play enclosures, flag as open if successful."""
        set_flag = bool(int(arg or 1))
        common.show_entry(self.entry, verbose=2)
        common.download_enclosures(self.entry)
        common.normalize_enclosures(self.entry)
        common.play_enclosures(self.entry, set_flag=set_flag)
        self.feed.write()

    def do_remove(self, arg):
        """Remove enclosures."""
        try:
            set_flag = bool(int(arg or 1))
            common.remove_enclosures(self.entry, set_flag=set_flag)
            self.entry.feed.write()
        except ValueError as e:
            messager.feedback(e)

    def do_set(self, arg):
        """Set entry flag."""
        if not arg:
            messager.feedback('Argument needed.')
        else:
            self.entry.set_flag(arg)
            self.feed.write()

    def do_setprogress(self, arg):
        """Set entry flag."""
        if not arg:
            messager.feedback('Argument needed.')
        else:
            self.entry.progress = int_or_float(arg)
            self.feed.write()

    def do_seen(self, arg):
        """Set fresh as new."""
        entries = self.entries if arg == 'all' else [self.entry]
        for e in entries:
            if e.flag == Flag.fresh:
                s = 'Flagging {0.flag} entry as new: {}'.format(e)
                messager.feedback(s)
                e.set_flag(Flag.new)
                e.feed.write()

    def do_zoom(self, arg):
        """Zoom to feed."""
        viewstring = arg or ''
        d = dict(self.view, directory=[self.feed.directory], number=-1)
        view = View(**d)
        view = view.parse(viewstring)
        messager.msg('Zooming to feed "{}"'.format(self.feed.directory))
        ui = UI(self.proc, view=view)
        ui.run()
        messager.msg('Returning to {} feeds'.format(len(self.view.directory)))

    def do_update(self, arg):
        """Update view."""
        viewstring = arg or ''
        self.view = self.view.parse(viewstring)
        guid, url = self.entry.guid, self.feed.url
        self.read_data()
        self.jump(guid, url)

    def do_sync(self, arg):
        """General synchronize."""
        if not arg:
            messager.feedback('Argument needed.')
        what = arg
        if what == 'read':
            self.read_data(force=True)
        if what == 'write':
            self.write_data(force=True)
        if what == 'refresh':
            n = self.feed.refresh()
            messager.msg(n)
            # TODO

    do_N = do_nextfeed
    do_b = do_back
    do_dl = do_download
    do_g = do_go
    do_l = do_list
    do_n = do_next
    do_nl = do_normalize
    do_p = do_play
    do_q = do_quit = do_EOF
    do_rm = do_remove
    do_s = do_search
    do_setp = do_setprogress
    do_u = do_update
    do_v = do_view
    do_z = do_zoom


def int_or_float(x):
    x = float(x)
    if x.is_integer():
        return int(x)
    return x


# Testing.
# class CmdUI(cmd.Cmd):
#     intro = 'Welcome'
#     prompt = '>>> '
#     separator = ';'  # Separator for multiple commands on one line.
#
#     def preloop(self):
#         print('pre')
#
#     def postloop(self):
#         print('post')
#
#     def precmd(self, line):
#         print('precmd', line)
#         lines = line.split(self.separator)
#         first = lines.pop(0)
#         self.cmdqueue.extend(lines)
#         return first
#
#     def do_EOF(self, arg):
#         """Quit."""
#         return True
#
#     do_bye = do_EOF
#
#     def do_foo(self, arg):
#         """jees"""
#         print('foobar: -{}-'.format(arg))
#
#     def do_bar(self, arg):
#         """jees nbar"""
#         print('bar')
#
#     # def complete_foo(self, text, line, begidx, endidx):
#     #     lst = list(globals().keys())
#     #     return [x for x in lst if x.startswith(text)]
