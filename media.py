"""Media files."""

import datetime
import json
import logging
import shlex
import subprocess
import tempfile
import webbrowser
from pathlib import Path

from pyutils.files import XAttr, move
from pyutils.misc import fmt_args

log = logging.getLogger(__name__)


def call(args):
    log.info('Running: %s', ' '.join(args))
    return subprocess.call(args)


def check_output(args, **kwargs):
    log.info('Running: %s', ' '.join(args))
    try:
        return subprocess.check_output(args, universal_newlines=True, **kwargs)
    except FileNotFoundError as e:
        log.error('Command not found: %s', args[0])
        return None
    except subprocess.CalledProcessError as e:
        log.error('Subprocess returned error: %i:', e.returncode)
        log.error(e.output)
        return None


def download_yle(url, path, sublang='all', tmpdir=None):
    """Download file from Yle Areena. Return True if succesful."""
    if tmpdir is None:
        with tempfile.TemporaryDirectory(suffix='.tmp', prefix='yledl-') as t:
            return download_yle(url, path, sublang=sublang, tmpdir=t)

    path = Path(path)
    tmpdir = Path(tmpdir)
    stream = tmpdir / 'stream'  # TODO: New yle-dl breaks -o.
    args = fmt_args('yle-dl --sublang {sublang} -o {o} {url}', sublang=sublang,
                    o=stream.name, url=url)
    logging.debug(args)
    output = check_output(args, stderr=subprocess.STDOUT, cwd=tmpdir)
    if output is None:
        return False

    # Move media file to destination.
    move(stream, path)

    # Move any subtitles, too.
    for sub in iter_subfiles(stream):
        new_suffix = ''.join(sub.suffixes)
        dst = path.with_suffix(new_suffix)
        log.info('Moving subfile: %s', dst)
        move(sub, dst)
    return True


def iter_subfiles(path):
    """Glob any subtitle files downloaded with mediafile."""
    pattern = '{}.*.srt'.format(path.name)
    subs = path.parent.glob(pattern)
    return subs


def get_media_info(path):
    """Return information about media file as a dictionary."""
    s = '''ffprobe
        -hide_banner -loglevel fatal
        -of json
        -show_format -show_error
        -show_streams -show_data
        -show_programs -show_chapters
        {path}
        '''
    args = fmt_args(s, path=path)
    output = check_output(args)
    if output is None:
        return None
    info = json.loads(output)
    return info


def get_duration(path):
    """Return media duration in seconds."""
    d = get_media_info(path)
    try:
        seconds = float(d['format']['duration'])
    except (AttributeError, TypeError):
        return None
    return datetime.timedelta(seconds=seconds)


def normalize_volume(path):
    """Normalize volume."""
    # args = fmt_args('volnorm -s {path}', path=path)
    cmd = 'volnorm -s {path}'.format(path=shlex.quote(str(path)))
    args = shlex.split(cmd)
    return call(args)


def get_gain(path):
    """Get ReplayGain level."""
    key = 'user.loudness.replaygain_track_gain'
    try:
        attrs = XAttr(path)
        value, unit = attrs[key].decode('ascii').split()
        value = float(value)
        return value, unit
    except (KeyError, FileNotFoundError):
        return None


def fmt_gain(gain):
    """Format gain info. See get_gain()."""
    return ''.join(str(x) for x in gain) if gain else str(gain)


def play_file(path):
    """Play media."""
    gain = get_gain(path)
    if gain:
        s = 'replaygain-fallback={}'.format(gain[0])
    else:
        s = 'detach'
    af = '--af=volume=replaygain-track:{}'.format(s)
    # args = fmt_args('mpv {af} {path}', af=af, path=path)
    ad = '--audio-display=no'
    cmd = 'mpv {af} {ad} {path}'.format(af=af, ad=ad,
                                        path=shlex.quote(str(path)))
    args = shlex.split(cmd)
    return call(args)


def play_stream(url):
    """Play media."""
    af = '--af=volume=replaygain-track:detach'
    ad = '--audio-display=no'
    args = fmt_args('mpv {af} {ad} {url}', af=af, ad=ad, url=url)
    return call(args)


def open_link(url, **kwargs):
    """Open entry link in web browser."""
    webbrowser.open(url, **kwargs)