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

_sync() {
    # Sync files with Jolla.
    tmp="$(_tmpfile)"
    nfiles=15
    prefix="$1"
    dst="$HOME/jolla/Music/podcasts/$prefix"

    #dirs="$(echo $HOME/podcasts/!(complete*|done*|music*|video*))"
    #dirs="$(echo $HOME/podcasts/!(complete*|done*|video*))"
    dirs="$(echo $HOME/podcasts/$prefix*)"
    cmd="podxm -c show_files -w in,1,SD, -d $dirs"

    $cmd | grep '\.\(mp3\|ogg\)' | head -n $nfiles > "$tmp"
    echo "Prefix: $prefix, files: $(wc -l < $tmp), size: $(xargs du -ch < $tmp | tail -n 1)"

    #less "$tmp"
    mkdir -p "$dst"
    rm -rf "$dst"/*
    xargs ln -f -t "$dst" < "$tmp"
    du -h "$dst"
    rm "$tmp"
}

do_param() {
    case "$1" in
    ui)
        # podxm -c ui -w ,1,D,SD -d !(music*)
        podxm -c ui -w ,1,D,SD -d $dirs_nomusic
        ;;
    ui-m)
        # podxm -c ui -w ,1,d,Sd -d music*
        podxm -c ui -w ,1,d,Sd -d $dirs_music
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
        _nice podxm -c dl norm -w in,3,D,SD -d $dirs_nomusic
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
        _sync 0current
        _sync complete
        _sync history
        _sync misc
        _sync music
        du -hcs "$HOME/jolla/Music/podcasts"
        ;;
    src)
        $VISUAL $0
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
    do_param $param
done
