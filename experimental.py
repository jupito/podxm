"""Experimental stuff."""

from contextlib import contextmanager
import logging
import os
import subprocess

import files
import ui_cmd


log = logging.getLogger(__name__)


def menu(entries):
    """External menu."""
    # TODO
    args = 'dmenu -i -l 20'.split()
    try:
        # p = subprocess.Popen(args, universal_newlines=True,
        #                      stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        # output = p.communicate('\n'.join(str(entries)))
        text = '\n'.join(entries)
        output = subprocess.check_output(args, universal_newlines=True,
                                         input=text)
        return output
    except subprocess.CalledProcessError as e:
        log.error('Subprocess returned code %i:', e.returncode)
        log.debug(e.output)
        return e.output


class MenuUI(ui_cmd.UI):
    """Line-oriented UI that uses external menu."""
    def get_line(self):
        cmds = ['q', 'g', 's']
        entries = ['{:2d} : {}'.format(i, x) for i, x in
                   enumerate(self.entries)]
        output = menu(cmds + entries)
        ui_cmd.feedback(output)
        words = output.split()
        if words[0].isdigit():
            self.i = int(words[0])
        return output


@contextmanager
def open_cfg(path):
    """Context manager for opening a configuration file."""
    path = os.path.expandvars(os.path.expanduser(path))
    if os.path.exists(path):
        cfg = files.read_data(path)
    else:
        cfg = dict()
    yield cfg
    files.write_data(path, cfg)


def generate_guid(fp):
    """Generate replacement for missing entry GUID."""
    if fp.enclosures:
        guid = fp.enclosures[0]['href']
        if guid:
            log.warning('Used enclosure URL for missing entry GUID: %s', guid)
            return guid
    guid = '{};{};{:x}'.format(get_date(fp), quote(fp.get('link'), ''),
                               hash(fp.get('title')))
    log.warning('Cooked up this for missing entry GUID: %s', guid)
    return guid
