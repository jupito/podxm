#!/bin/ksh

prg="podxm"
param=$1
test $param || param=ui

case "$param" in
ui)
    cmd="$prg -c ui -w ,D,1,SD -d !(music*)"
    ;;
ui-music)
    cmd="$prg -c ui -w ,d,1,Sd -d music*"
    ;;
ui-iot)
    cmd="$prg -c ui -w foin,d,-1,d -d 'misc,dl=0/In Our Time'*"
    ;;
ref)
    cmd="parallel-moreutils -j10 -n10 $prg -c refresh -d -- */*"
    ;;
dl)
    # # $prg -c dl -w fn,fpD,3, -d !(music*)
    # $prg -c dl -w foina,D,3, -d !(music*)
    # $prg -c norm -w foina,,-1, -d !(music*)
    dir="!(music*)"
    view="foina,D,3,"
    cmd1="$prg -c dl -w $view -d $dir"
    cmd2="$prg -c norm -w $view -d $dir"
    cmd="$cmd1 && $cmd2"
    ;;
dl-music)
    dir="music*"
    view="n,d,5,"
    cmd1="$prg -c dl -w $view -d $dir"
    cmd2="$prg -c norm -w $view -d $dir"
    cmd="$cmd1 && $cmd2"
    ;;
dl-ia)
    cmd1="$prg -c dl -w ia,SD,-1, --force -d *"
    cmd2="$prg -c norm -w foina,SD,-1, -d *"
    cmd="$cmd1 && $cmd2"
    ;;
src)
    $VISUAL $0
    exit
    ;;
*)
    print "Unknown parameter: $1"
esac

cd $HOME/podcasts
print "Running: $cmd"
eval "$cmd"
