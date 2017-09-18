#!/bin/sh

# Run podxm.

set -e

cd "$HOME/podcasts"

#dirs_talk="$(find . -mindepth 1 -maxdepth 1 -type d \! -ipath './music*')"
#dirs_music="$(find . -mindepth 1 -maxdepth 1 -type d -ipath './music*')"

_dirs_talk() {
    find . -mindepth 1 -maxdepth 1 -type d \! -ipath './music*'
}

_dirs_music() {
    find . -mindepth 1 -maxdepth 1 -type d -ipath './music*'
}

_dirs_video() {
    find . -mindepth 1 -maxdepth 1 -type d -ipath './video*'
}

_dirs_current() {
    echo 0current*
}

_dirs_iot() {
    # dirs="$(find . -mindepth 2 -maxdepth 2 -type d -iname 'in our time*' -printf '%P'\ )"
    echo ./*/in_our_time*
}

_tmpfile() {
    prg="$(basename "$0")"
    mktemp -u --tmpdir "tmp.$prg.XXXXXXXXXX"
}

_nice() {
    nice ionice -c3 "$@"
}

_du() {
    size="$(du -hs "$1")"
    nfiles="$(find "$1" -type f | wc -l)"
    echo "$nfiles files, $size"
}

_refresh() {
    # Refresh all feeds in parallel.
    #parallel-moreutils -j10 -n10 podxm -c refresh -d -- */*
    #find . -mindepth 2 -type d -print0 | xargs -0 -L10 -P10 podxm -c refresh -d
    find . -mindepth 2 -type d -print0 | xargs -0 -L25 -P4 podxm -c refresh -d
}

_sync_playlists() {
    playlistdir=Music/playlists
    mkdir -p ~/jolla/$playlistdir
    cp -a ~/$playlistdir/* ~/jolla/$playlistdir
}

_sync_podcasts() {
    # Sync files with Jolla.
    tmp="$(_tmpfile)"
    n=15
    prefix="$1"
    dst="$HOME/jolla/Music/podcasts/$prefix"

    # Previously, Ksh is used because sh/dash doesn't support "!(music()".
    #dirs="$(echo $HOME/podcasts/!(complete*|done*|music*|video*))"
    #dirs="$(echo $HOME/podcasts/!(complete*|done*|video*))"
    dirs="$(echo $HOME/podcasts/$prefix*)"
    cmd="podxm -c show_files -w oin,1,D,D -d $dirs"

    $cmd | grep '\.\(mp3\|ogg\)' | head -n $n > "$tmp"

    #nfiles="$(wc -l < $tmp)"
    #size="$(xargs du -chs < $tmp | tail -n 1)"
    #echo "$prefix: $nfiles files, "$size""

    #less "$tmp"
    mkdir -p "$dst"
    rm -rf "${dst:?}"/*
    xargs ln -f -t "$dst" < "$tmp"
    rm "$tmp"
    _du "$dst"
}

do_param() {
    case "$1" in
    ref|refresh)
        _refresh
        ;;
    ui-t)
        podxm -c ui -w ,1,SD,SD -d $(_dirs_talk)
        ;;
    ui-m)
        podxm -c ui -w ,1,Sd,Sd -d $(_dirs_music)
        ;;
    ui-v)
        podxm -c ui -w ,1,Sd,Sd -d $(_dirs_video)
        ;;
    ui-f)
        podxm -c ui -w f,-1,SD,SD -d ./*
        ;;
    ui-c)
        podxm -c ui -w ,1,D,SD -d $(_dirs_current)
        ;;
    ui-iot)
        podxm -c ui -w foin,-1,d,d -d $(_dirs_iot)
        ;;
    dl-t)
        _nice podxm -c dl norm -w n,3,D,SD -d $(_dirs_talk)
        ;;
    dl-m)
        _nice podxm -c dl norm -w n,3,d,Sd -d $(_dirs_music)
        ;;
    dl-i)
        _nice podxm -c dl norm -w oia,-1,,SD --force -d ./*
        ;;
    norm)
        _nice podxm -c norm -w foina,-1,,SD -d ./*
        ;;
    check)
        _nice podxm -c check -w foinad,-1,, -d .
        ;;
    sync)
        _sync_playlists
        _sync_podcasts 0current
        _sync_podcasts complete
        _sync_podcasts history
        _sync_podcasts misc
        _sync_podcasts music
        _du ~/jolla/Music/podcasts
        ;;
    help)
        grep '^\s\+[-|a-z]\+)' "$0"
        ;;
    src)
        $VISUAL "$0"
        exit
        ;;
    *)
        echo "Unknown parameter: $1"
        exit 1
        ;;
    esac
}

for param; do
    echo "#### $param"
    do_param "$param"
done
