#!/bin/ksh

# Run podxm. Ksh is used because sh/dash doesn't support "!(music()".

do_param() {
    param="$1"
    set -x
    case "$param" in
    ui)
        podxm -c ui -w ,D,1,SD -d !(music*)
        ;;
    ui-m)
        podxm -c ui -w ,d,1,Sd -d music*
        ;;
    ui-iot)
        podxm -c ui -w foin,d,-1,d -d 'misc,dl=0/In Our Time'*
        ;;
    ref)
        parallel-moreutils -j10 -n10 podxm -c refresh -d -- */*
        ;;
    dl)
        podxm -c dl -w in,D,3,SD -d !(music*)
        nice podxm -c norm -w in,D,3,SD -d !(music*)
        ;;
    dl-m)
        podxm -c dl -w in,d,5,Sd -d music*
        nice podxm -c norm -w in,d,5,Sd -d music*
        ;;
    dl-ia)
        podxm -c dl -w ia,,-1,SD --force -d *
        nice podxm -c norm -w foina,,-1,SD -d *
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

set -e

cd $HOME/podcasts

for param; do
    echo "#### $param"
    do_param $param
done
