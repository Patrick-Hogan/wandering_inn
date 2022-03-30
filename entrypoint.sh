#!/bin/bash

# Select output (default: latest chapter only)
if [[ -z $1 ]]; then
    ./wanderinginn2epub.py --output-by-chapter --chapter latest | grep "successfully generated"
else
    ./wanderinginn2epub.py $* | grep "successfully generated"
fi

# convert all epubs that don't already have mobi version to mobi
for book in ./build/*.epub; do
    if [[ ! -f "${book/epub/mobi}" ]]; then
        ebook-convert "$book" "${book/epub/mobi}"
    fi
done

