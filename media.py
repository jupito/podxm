"""Media files."""

import datetime
import json
import logging
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence, Tuple, Union

from pyutils.files import XAttrStr, move
from pyutils.misc import fmt_args

log = logging.getLogger(__name__)


def call(args: Sequence[str]) -> int:
    log.info('Running: %s', ' '.join(args))
    return subprocess.call(args)


def check_output(args: Sequence[str], **kwargs) -> str:
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


def download_yle(url: str, path: Path, sublang: str = None,
                 tmpdir: Path = None) -> bool:
    """Download file from Yle Areena. Return True if succesful.

    `sublang` can be fin, swe, smi, none or all.
    """
    if tmpdir is None:
        with tempfile.TemporaryDirectory(suffix='.tmp', prefix='yledl-') as t:
            return download_yle(url, path, sublang=sublang, tmpdir=Path(t))

    if sublang is None:
        sublang = 'fin'
    # path = Path(path)
    # tmpdir = Path(tmpdir)
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


def iter_subfiles(path: Path) -> Iterable[Path]:
    """Glob any subtitle files downloaded with mediafile."""
    pattern = '{}.*.srt'.format(path.name)
    return path.parent.glob(pattern)


def get_media_info(path: Path) -> dict:
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
    return json.loads(output)


def get_duration(path: Path) -> Union[datetime.timedelta, None]:
    """Return media duration in seconds."""
    d = get_media_info(path)
    try:
        seconds = float(d['format']['duration'])
    except (AttributeError, TypeError):
        return None
    return datetime.timedelta(seconds=seconds)


def normalize_volume(path: Path) -> int:
    """Normalize volume."""
    # args = fmt_args('volnorm -s {path}', path=path)
    cmd = 'volnorm -s {path}'.format(path=shlex.quote(str(path)))
    args = shlex.split(cmd)
    return call(args)


def get_gain(path: Path) -> Union[Tuple[float, str], None]:
    """Get ReplayGain level."""
    key = 'user.loudness.replaygain_track_gain'
    try:
        attrs = XAttrStr(path)
        value, unit = attrs[key].split()
        value = float(value)
    except (FileNotFoundError, KeyError):
        return None
    except ValueError:
        log.warning('Invalid ReplayGain value "%s" in "%s"', value, path)
        return None
    return value, unit


def fmt_gain(gain: Tuple[float, str]) -> str:
    """Format gain info. See get_gain()."""
    return ''.join(str(x) for x in gain) if gain else str(gain)


def play_file(path: Path) -> int:
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


def play_stream(url: str) -> int:
    """Play media."""
    af = '--af=volume=replaygain-track:detach'
    ad = '--audio-display=no'
    args = fmt_args('mpv {af} {ad} {url}', af=af, ad=ad, url=url)
    return call(args)


# def open_link(url, **kwargs):
#     """Open entry link in web browser."""
#     webbrowser.open(url, **kwargs)
