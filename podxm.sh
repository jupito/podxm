#!/bin/sh

# Run podxm.

set -e

# shellcheck disable=SC1090
. ~/bin/def.sh

njobs=2
podcasts_dir=~/podcasts
playlist_dir=~/Music/playlists
portable_podcasts_dir=~/jolla/Music/podcasts
portable_playlist_dir=~/jolla/Music/playlists

_xe() { reallynice xe -j "$njobs" "$@"; }
_xe1() { reallynice xe -j 1 "$@"; }

_du() {
    size="$(du -hs "$1")"
    nfiles="$(find "$1" -type f | wc -l)"
    echo "$nfiles files, $size"
}

_dirs() {
    case "_$1" in
    _all)
        find . -maxdepth 1
        ;;
    _fic)
        find ./* -mindepth 1 -maxdepth 1 -type d -ipath '*/fiction*'
        ;;
    _talk)
        #dirs_talk="$(find . -mindepth 1 -maxdepth 1 -type d \! -ipath './music*')"
        # find . -mindepth 2 -maxdepth 2 -type d \! -ipath '*/music*' \! -ipath '*/video*'
        find ongoing* -mindepth 1 -maxdepth 1 -type d \! -ipath '*/music*' \! -ipath '*/video*'
        ;;
    _music)
        #dirs_music="$(find . -mindepth 1 -maxdepth 1 -type d -ipath './music*')"
        #find ongoing* -mindepth 1 -maxdepth 1 -type d -ipath '*/music*'
        find ./* -mindepth 1 -maxdepth 1 -type d -ipath '*/music*'
        ;;
    _video)
        find ./* -mindepth 1 -maxdepth 1 -type d -ipath '*/video*'
        ;;
    _current)
        echo ongoing*/0current*
        ;;
    _complete)
        find complete* -mindepth 1 -maxdepth 1 -type d \! -ipath '*/music*' \! -ipath '*/video*'
        ;;
    _done)
        find done* -mindepth 1 -maxdepth 1 -type d \! -ipath '*/music*' \! -ipath '*/video*'
        ;;
    _iot)
        # dirs="$(find . -mindepth 2 -maxdepth 2 -type d -iname 'in our time*' -printf '%P'\ )"
        echo ./*/*/in_our_time*
        ;;
    *)
        eecho "Invalid directory specifier: $1"
        exit 1
        ;;
    esac
}

call_refresh() {
    # Refresh all feeds in parallel.
    #parallel-moreutils -j10 -n10 podxm -c refresh -d -- */*
    #find . -mindepth 2 -type d -print0 | xargs -0 -L25 -P4 podxm -v -c refresh -d
    ##nlines=10
    #nlines=1
    #find ongoing* -mindepth 2 -type d -print0 | xargs -0 -L"$nlines" -P"$njobs" podxm -c refresh -d
    find ongoing -mindepth 2 -type d | _xe podxm -c refresh -d
}

# shellcheck disable=SC2046
call_ui_t() { podxm -c ui -w ,1,D,SD -d $(_dirs talk); }
call_ui_c() { podxm -c ui -w ,1,d,Sd -d $(_dirs complete); }
#call_ui_m() { podxm -c ui -w ,2,SD=,Sd -d $(_dirs music); }
call_ui_m() { podxm -c ui -w ,2,SD,SD -d $(_dirs music); }
call_ui_fic() { podxm -c ui -w ,1,SD,SD -d $(_dirs fic); }
call_ui_v() { podxm -c ui -w ,1,SD,fSD -d $(_dirs video); }
call_ui_f() { podxm -c ui -w f,-1,,i -d ongoing/*; }
call_ui_af() { podxm -c ui -w f,-1,,i -d "./*"; }
call_ui_current() { podxm -c ui -w ,1,D,SD -d $(_dirs current); }
call_ui_d() { podxm -c ui -w foina,1,d,Sd -d $(_dirs 'done'); }
call_ui_iot() { podxm -c ui -w foin,-1,d,d -d $(_dirs iot); }

call_dl_t() { reallynice podxm -c dl -w n,1,D,SD -d $(_dirs talk); }
call_dl_c() { reallynice podxm -c dl -w n,1,d,Sd -d $(_dirs complete); }
call_dl_m() { reallynice podxm -c dl -w n,1,d,Sd -d $(_dirs music); }
call_dl_v() { reallynice podxm -c dl -w n,1,d,Sd -d $(_dirs video); }
call_dl_i() { reallynice podxm -c dl -w oia,-1,,SD --force -d ./*; }

#call_norm() { reallynice podxm -c norm -w foina,-1,,SD -d ./*; }
call_norm() { njobs=1 _dirs all | _xe1 podxm -c norm -w foina,-1,,SD -d; }
call_check() { _dirs all | _xe podxm -c check -w foinad,-1,, -d .; }  # TODO: Do only once

_sync_playlists() {
    echo "Syncing playlists..."
    mkdir -p "$portable_playlist_dir"
    cp -a "$playlist_dir"/* "$portable_playlist_dir"
}

_sync_podcasts() {
    # Sync files with portable device.
    #echo "Syncing podcasts: $0..."
    tmp="$(_tmpfile)"
    n=15
    prefix="$1"
    dst="$portable_podcasts_dir/$prefix"

    # Previously, Ksh is used because sh/dash doesn't support "!(music()".
    #dirs="$(echo $podcasts_dir/!(complete*|done*|music*|video*))"
    #dirs="$(echo $podcasts_dir/!(complete*|done*|video*))"
    #dirs="$(echo $podcasts_dir/ongoing/"$prefix"*)"
    dirs="$(echo $podcasts_dir/*/"$prefix"*)"
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

call_sync() {
    _sync_playlists
    _sync_podcasts 0current
    _sync_podcasts fiction
    _sync_podcasts history
    _sync_podcasts misc
    _sync_podcasts music
    _sync_podcasts science
    _du "$portable_podcasts_dir"
}

cd "$podcasts_dir"
do_args "$@"
