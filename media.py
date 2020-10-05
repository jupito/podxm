"""Media files."""

import datetime
import json
import logging
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence, Union

from misctypes import Gain
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
    except FileNotFoundError:
        log.error('Command not found: %s', args[0])
        return None
    except subprocess.CalledProcessError as e:
        log.error('Subprocess returned error: %i:', e.returncode)
        log.error(e.output)
        return None


def download_yle(url: str, path: Path, sublang: str = None,
                 tmpdir: Path = None, verbose: bool = True,
                 # backend: str = 'youtubedl,rtmpdump'
                 backend: str = 'wget,ffmpeg'
                 ) -> bool:
    """Download file from Yle Areena. Return True if succesful.

    `sublang` can be fin, swe, smi, none or all. TODO: changed???
    """
    if tmpdir is None:
        with tempfile.TemporaryDirectory(suffix='.tmp', prefix='yledl-') as t:
            return download_yle(url, path, sublang=sublang, tmpdir=Path(t))

    if verbose:
        print(f'Downloading: {path}')
    if sublang is None:
        sublang = 'all'
    # path = Path(path)
    # tmpdir = Path(tmpdir)
    # stream = tmpdir / 'stream.flv'
    stream = tmpdir / 'stream'
    # s = 'yle-dl --backend {be} --sublang {sublang} -o {o} {url}'
    s = 'yle-dl --sublang {sublang} --maxbitrate best -o {o} {url}'
    d = dict(be=backend, sublang=sublang, o=stream.name, url=url)
    args = fmt_args(s, **d)
    logging.debug(args)
    output = check_output(args, stderr=subprocess.STDOUT, cwd=tmpdir)
    if output is None:
        return False

    # Move media file to destination.
    # move(stream.with_suffix('.flv'), path)
    # TODO: Horrible kludge to adapt to varying prefix.
    try:
        move(stream.with_suffix('.flv'), path)
    except FileNotFoundError:
        move(stream.with_suffix('.mp3'), path.with_suffix('.mp3'))
        # try:
        #     move(stream.with_suffix('.mp3'), path.with_suffix('.mp3'))
        # except FileNotFoundError:
        #     move(stream.with_suffix('.mp4'), path.with_suffix('.mp4'))

    # Move any subtitles, too.
    for sub in iter_subfiles(stream):
        new_suffix = ''.join(sub.suffixes)
        dst = path.with_suffix(new_suffix)
        log.info('Moving subfile: %s', dst)
        move(sub, dst)
    return True


def iter_subfiles(path: Path) -> Iterable[Path]:
    """Glob any subtitle files downloaded with mediafile."""
    return path.parent.glob(f'{path.name}.*.srt')


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
    quoted = shlex.quote(str(path))
    cmd = f'volnorm -s {quoted}'
    args = shlex.split(cmd)
    return call(args)


def get_gain(path: Path) -> Union[Gain, None]:
    """Get ReplayGain level."""
    key = 'user.loudness.replaygain_track_gain'
    try:
        attrs = XAttrStr(path)
        gain = Gain.parse(attrs[key])
    except (FileNotFoundError, KeyError):
        return None
    except ValueError:
        log.exception('Invalid ReplayGain value: %s', path)
        return None
    return gain


def play_file(path: Path, start=None) -> int:
    """Play media."""
    gain = get_gain(path)

    # # XXX: Deprecated.
    # if gain:
    #     s = 'replaygain-fallback={}'.format(gain.value)
    # else:
    #     s = 'detach'
    # af = '--af=volume=replaygain-track:{}'.format(s)

    rp = '--replaygain=track'
    if gain:
        fb = f'--replaygain-fallback={gain.value}'
    else:
        fb = ''

    ad = '--audio-display=no'

    if start is not None:
        st = f'--start={start * 100}%'
    else:
        st = ''

    quoted = shlex.quote(str(path))
    cmd = f'mpv {rp} {fb} {ad} {st} {quoted}'
    args = shlex.split(cmd)
    return call(args)


def play_stream(url: str) -> int:
    """Play media."""
    # TODO: Obsolete, replace wth `stream()`. Just check those arguments...
    af = '--af=volume=replaygain-track:detach'
    ad = '--audio-display=no'
    args = fmt_args('mpv {af} {ad} {url}', af=af, ad=ad, url=url)
    return call(args)


def stream(url):
    """Stream media."""
    args = fmt_args('0stream {url}', url=url)
    return call(args)
