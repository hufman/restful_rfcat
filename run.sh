#!/bin/sh

real=`realpath "$0"`
cd "`dirname "$real"`"

exec python -m restful_rfcat.main
