#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  5 01:19:53 2018
@author: Patrick
"""

from urllib.request import urlopen
import os
from bs4 import BeautifulSoup
import json
import codecs

from ebookmaker.ebookmaker import OPFGenerator, parseEBookFile

toc = r'https://wanderinginn.com/table-of-contents/'
chapter_file = 'the_wandering_inn/chapters.json'
html_path = os.path.join('the_wandering_inn', 'html')

html = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11\
/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="author" content="pirate aba">
<meta name="description" content="The Wandering Inn">
<meta name="classification" content="Fantasy" >
<title>The Wandering Inn</title>
<link rel="stylesheet" href="style.css" type = "text/css" />
</head>
<body>
'''

global extracted_chapters
extracted_chapters = dict()

def get_chapter(chapter_id, url):
    global extracted_chapters
    if str(url) in extracted_chapters:
        print("Already downloaded {0}: Skipping".format(url))
        return

    response = urlopen(url)
    pg = BeautifulSoup(response, 'lxml')
    contents = pg.find('div', {'class': 'entry-content'})
    end_content = contents.find("hr")

    if end_content:
        [s.decompose() for s in end_content.find_next_siblings()]
        end_content.decompose()

    title = pg.find('h1', {'class':'entry-title'}).text.strip()
    if title == "Glossary":
        chapter_id = 999999
        file_name = "Glossary.html"
    else:
        #file_name = 'chapter_{0}_{1}.html'.format(ix, chapter_id)
        file_name = 'wandering_inn-{0:03d}.html'.format(chapter_id)
        file_name = os.path.join(html_path, file_name)
        h1 = pg.new_tag("h1", id=chapter_id)
        h1.string = title

        # Strip color from text that can make it hard to read on a paperwhite:
        for span in contents.find_all('span'):
            if 'color' in str(span):
                span.replaceWithChildren()

        # And replace images that can't be rendered:
        for img in contents.find_all('img'):
            r = pg.new_tag('p')
            r.string = "IMAGE REMOVED"
            img.replace_with(r)

        print("Writing {0}: {1}".format(chapter_id, title))
        with codecs.open(file_name, 'w', encoding='utf-8') as fh:
            fh.write(html)
            fh.write(str(h1))
            fh.write(str(contents))
            fh.write('</p>\n\n</body>\n</html>\n')
        extracted_chapters[url] = chapter_id


def get_index():
    page = urlopen(toc)
    soup = BeautifulSoup(page, 'lxml')
    # index = soup.find('div', {'class': 'entry-content'})
    index = soup.find('p')
    links = index.find_all_next('a', href=True)
    return links

def get_book():
    try:
        if os.path.isfile(chapter_file):
            with open(chapter_file, 'r') as fh:
                global extracted_chapters
                extracted_chapters = json.load(fh)
    except Exception as error:
        print("Error loading chapter json: {0}".format(error))

    links = get_index()
    # get_chapter(0, 'https://wanderinginn.com/2016/07/27/1-00/')
    for chapter_id, link in enumerate(links, 1):
        try:
            get_chapter(chapter_id, link['href'])
        except Exception as error:
            print("Error converting {0}: {1}".format(chapter_id, error))
    with open(chapter_file, 'w') as fh:
        json.dump(extracted_chapters, fh)

def main():
    get_book()
    ebook_data = parseEBookFile( 'the_wandering_inn/the_wandering_inn.json')
    gen = OPFGenerator(ebook_data)
    gen.createEBookFile('the_wandering_inn/The Wandering Inn.epub')

if __name__ == "__main__":
    main()
