#!/bin/bash

if [[ -z $1 ]]; then
    echo Usage: $0 BOOK.epub
    if [[ -z $RECIPIENTS ]]; then
        echo Will convert epub to mobi and send to all addresses in recipients.txt
    else
        echo Will convert epub to mobi and send to $RECIPIENTS
    fi
    exit 1
fi

if [[ -z $RECIPIENTS ]]; then
    RECIPIENTS=$(sed '$!N; s/\n/ /g' recipients.txt)
fi

#python3 wanderinginn2epub.py || exit 1
book=${1/epub/mobi}
ebook-convert "$1" "${book}" || exit 1

if [[ ! -z $RECIPIENTS ]]; then
    echo Mailing to: $RECIPIENTS
    echo mutt -s "The Wandering Inn" "$RECIPIENTS" -a "$book"
    mutt -s "The Wandering Inn" $RECIPIENTS -a "$book" < /dev/null
else
    echo No recipients found. Specify as env, arg or in recipients.txt
fi
