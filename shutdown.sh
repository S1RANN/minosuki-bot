#! /bin/bash
MAIN=$(cat main.pid)

kill -15 $MAIN 