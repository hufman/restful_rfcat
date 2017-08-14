#!/bin/sh

real=`realpath "$0"`
cd "`dirname "$real"`"

python -m restful_rfcat.main
