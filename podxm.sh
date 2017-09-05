#!/bin/sh

# Run podxm. Ksh is used because sh/dash doesn't support "!(music()".

set -e

prg="$(basename $0)"
cd $HOME/podcasts
dirs_nomusic="$(find -mindepth 1 -maxdepth 1 -type d \! -ipath './music*')"
dirs_music="$(find -mindepth 1 -maxdepth 1 -type d -ipath './music*')"

_tmpfile() {
    mktemp -u --tmpdir tmp.$prg.XXXXXXXXXX
}

_nice() {
    nice ionice -c3 "$@"
}

_du() {
    size="$(du -hs "$1")"
    nfiles="$(find "$1" -type f | wc -l)"
    echo "$nfiles files, "$size""
}

_sync() {
    # Sync files with Jolla.
    tmp="$(_tmpfile)"
    n=15
    prefix="$1"
    dst="$HOME/jolla/Music/podcasts/$prefix"

    #dirs="$(echo $HOME/podcasts/!(complete*|done*|music*|video*))"
    #dirs="$(echo $HOME/podcasts/!(complete*|done*|video*))"
    dirs="$(echo $HOME/podcasts/$prefix*)"
    cmd="podxm -c show_files -w oin,1,SD, -d $dirs"

    $cmd | grep '\.\(mp3\|ogg\)' | head -n $n > "$tmp"

    # nfiles="$(wc -l < $tmp)"
    # size="$(xargs du -chs < $tmp | tail -n 1)"
    # echo "$prefix: $nfiles files, "$size""

    #less "$tmp"
    mkdir -p "$dst"
    rm -rf "$dst"/*
    xargs ln -f -t "$dst" < "$tmp"
    rm "$tmp"
    _du "$dst"
}

do_param() {
    case "$1" in
    ui)
        podxm -c ui -w ,1,D,SD -d $dirs_nomusic
        ;;
    ui-m)
        podxm -c ui -w ,1,Sd,Sd -d $dirs_music
        ;;
    ui-f)
        podxm -c ui -w f,-1,D,SD -d *
        ;;
    ui-iot)
        podxm -c ui -w foin,-1,d,d -d 'misc,dl=0/In Our Time'*
        # dirs="$(find -mindepth 2 -maxdepth 2 -type d -iname 'in our time*' -printf '%P'\ )"
        # podxm -c ui -w foin,-1,d,d -d $dirs
        ;;
    ref)
        # parallel-moreutils -j10 -n10 podxm -c refresh -d -- */*
        find -mindepth 2 -type d -print0 | xargs -0 -L10 -P10 podxm -c refresh -d
        ;;
    dl)
        _nice podxm -c dl norm -w n,3,D,SD -d $dirs_nomusic
        ;;
    dl-m)
        _nice podxm -c dl norm -w n,3,d,Sd -d $dirs_music
        ;;
    dl-i)
        _nice podxm -c dl norm -w oia,-1,,SD --force -d *
        ;;
    norm)
        _nice podxm -c norm -w foina,-1,,SD -d *
        ;;
    sync)
        rm -rf ~/jolla/Music/playlists
        cp -a ~/Music/playlists ~/jolla/Music
        _sync 0current
        _sync complete
        _sync history
        _sync misc
        _sync music
        _du ~/jolla/Music/podcasts
        ;;
    src)
        $VISUAL "$0"
        ;;
    *)
        echo "Unknown parameter: $1"
        exit 1
        ;;
    esac
}

for param; do
    echo "#### $param"
    do_param $param
done
