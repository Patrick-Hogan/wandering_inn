#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  5 01:19:53 2018
@author: Patrick
"""

from urllib.request import urlopen, URLError
import sys
import os
import argparse
import re
from copy import deepcopy
from bs4 import BeautifulSoup
import json
import codecs
import subprocess

from ebookmaker.ebookmaker import OPFGenerator


class Chapter:
    _HTML_HEADER = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11\
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

    def __init__(self, url, link_text='', volume=0, index=0):
        self.url = url
        self.name = link_text
        self.volume = volume
        self.index = index
        if self.name == 'Glossary':
            self.volume = 999999
            self.index  = 999999
        self.filename = f'wandering_inn-{self.volume:02d}.{self.index:03d}-{self.name}.html'

    def get_page(self):
        if self.url.startswith('http'):
            return urlopen(self.url, timeout=5)
        else:
            return open(self.url,'r')

    def save(self, stream=sys.stdout, strip_color=False, image_path='./images'):
        p = self.get_page()
        page = BeautifulSoup(p, 'lxml')

        contents = page.find('div', {'class': 'entry-content'})
        end_content = contents.find('hr')

        if end_content:
            [s.decompose() for s in end_content.find_next_siblings()]
            end_content.decompose()

        author_note = [p for p in contents.find_all('p') if p.getText()[0:6] == 'Author' and 'Note' in p.getText()[0:13]]
        if author_note:
            end_content = author_note[0]
            [s.decompose() for s in end_content.find_next_siblings()]
            end_content.decompose()

        if strip_color:
            # Strip color from text that can make it hard to read on a paperwhite:
            for span in contents.find_all('span'):
                if 'color' in str(span):
                    span.replaceWithChildren()

        # Download and replace image urls with local references:
        for img in contents.find_all('img'):
            img_filename = os.path.split(img['data-orig-file'])[1]
            with open(os.path.join(image_path, img_filename), 'wb') as fo:
                fo.write(urlopen(img['src'], timeout=5).read())
            img['src'] = os.path.join(image_path, img_filename)

        title = page.find('h1', {'class': 'entry-title'}).text.strip()
        h1 = page.new_tag('h1', id=self.index)
        h1.string = title

        print(f'{Chapter._HTML_HEADER}\n{h1}\n{contents}</p>\n\n</body>\n</html>\n',
              file=stream)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'Chapter<Volume: {self.volume}, Name: {self.name}, index: {self.index}>'

    def __lt__(self, other):
        if self.volume < other.volume:
            return True
        if self.volume == other.volume:
            if self.index < other.index:
                return True
        return False

    def __eq__(self, other):
        try:
            return (self.volume == other.volume and self.index == other.index)
        except AttributeError:
            return False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', dest='build_dir', default='./the_wandering_inn')
    parser.add_argument('--strip-color', dest='strip_color', action='store_true')
    parser.add_argument('--volume', default=[], type=int, nargs='+')
    parser.add_argument('--chapter', default=[], nargs='+')
    parser.add_argument('--by-chapter', dest='by_chapter', action='store_true')
    parser.add_argument('--toc-only', dest='toc_only', action='store_true')
    args = parser.parse_args()
    return args


def get_index(toc_url=r'https://wanderinginn.com/table-of-contents/'):
    page = urlopen(toc_url)
    soup = BeautifulSoup(page, 'lxml')
    paragraphs = soup.find_all('p')

    index = []
    volume = 0
    for v, chapters in zip(paragraphs[0::2], paragraphs[1::2]):
        try:
            volume = int(v.text.replace("Volume","").strip())
        except ValueError:
            print(f"Unable to get volume from text: {v}")
        index.extend([Chapter(link['href'], link.text, volume, index) for index, link in enumerate(chapters.find_all('a', href=True),1)])
    return index


def create_cover_image(base_image, title):
    impath, base_name = os.path.split(base_image)
    ext = os.path.splitext(base_name)[1]
    new_name = title.replace(' ', '_')
    new_image = os.path.join(impath, new_name + ext)
    subprocess.run(['convert',
                    '-pointsize', '40',
                    '-fill', 'yellow',
                    '-draw', f'text 10,72 "{title}"',
                    f'{base_image}',
                    f'{new_image}'])
    return new_image


def get_book(ebook_data,
             volume=None,
             index=None,
             chapter_match=None,
             strip_color=False,
             html_path=os.path.join('the_wandering_inn', 'html'),
             ):

    if index is None:
        index = get_index()

    add_all = volume is None and chapter_match is None

    if volume is not None:
        title = ebook_data['title'] + f' - Volume {volume}'

    ch = None
    if chapter_match:
        if chapter_match == 'latest':
            ch = index[-1]
        elif isinstance(chapter_match, Chapter):
            ch = chapter_match
        else:
            try:
                ch = [c for c in index if c.name == chapter_match][-1]
                print(f'Found matching chapter for {chapter_match}: {ch}')
            except Exception as error:
                print(f'Unable to find matching chapter for {chapter_match}')
                raise error
        title = ebook_data['title'] + f' - Volume {ch.volume}.{ch.index} - Chapter {ch.name}'

    cover = create_cover_image(ebook_data['cover'], title)
    ebook_data['title'] = title
    ebook_data['cover'] = cover

    if not os.path.isdir(html_path):
        os.makedirs(html_path)

    image_path = os.path.join(html_path, 'images')
    if not os.path.isdir(image_path):
        os.makedirs(image_path)
    for chapter in index:
        if add_all or volume == chapter.volume or ch == chapter:
            filename = os.path.join(html_path, chapter.filename)
            ebook_data['contents'].append({'generate': False, 'type': 'text', 'source': filename})
            if not os.path.isfile(filename):
                try:
                    with codecs.open(filename, 'w', encoding='utf-8') as fh:
                        chapter.save(stream=fh, strip_color=strip_color, image_path=image_path)
                except URLError as err:
                    os.unlink(filename)
                    raise err


def main():
    args = parse_args()

    with open('the_wandering_inn.json') as fh:
        ebook_data = json.load(fh)

    #replace_strings(ebook_data, '{BUILD_DIR}', args.build_dir)

    # # General assumption: create books by volume, with last volume (except glossary) by chapter
    # # For the whole book at once, just use:
    # get_book(ebook_data, html_path=os.path.join(args.build_dir, 'html'))

    index = get_index()

    if args.chapter:
        pass
    elif not args.volume:
        args.volume = set([c.volume for c in index])

    html_path = os.path.join(args.build_dir, 'html')

    for volume in args.volume:
        if args.by_chapter:
            for chapter in index:
                if chapter.volume != volume:
                    continue
                chapter_data = deepcopy(ebook_data)
                get_book(chapter_data,
                         volume=volume,
                         index=[chapter],
                         chapter_match=chapter.name,
                         html_path=html_path,
                         )
                gen = OPFGenerator(chapter_data)
                gen.createEBookFile(os.path.join(args.build_dir, f'{chapter_data["title"]}.epub'))
        else:
            volume_data = deepcopy(ebook_data)
            get_book(volume_data,
                    volume=volume,
                    index=index,
                    html_path=html_path,
                    )
            gen = OPFGenerator(volume_data)
            gen.createEBookFile(os.path.join(args.build_dir, f'{volume_data["title"]}.epub'))

if __name__ == "__main__":
    main()
