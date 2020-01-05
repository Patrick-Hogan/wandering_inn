#!/bin/bash

book="the_wandering_inn/The Wandering Inn.mobi"

if [[ -z $RECIPIENTS ]]; then RECIPIENTS="$*"; fi
if [[ -z $RECIPIENTS ]]; then
    RECIPIENTS=$(sed 's/\n/ /g' recipients.txt)
fi

python3 wanderinginn2epub.py || exit 1
ebook-convert "the_wandering_inn/The Wandering Inn.epub" "$book" || exit 1

if [[ ! -z $RECIPIENTS ]]; then
    echo Mailing to: $RECIPIENTS
    mutt -s "The Wandering Inn" $recipients -a "$book" < /dev/null
else
    echo No recipients found. Specify as env, arg or in recipients.txt
fi
