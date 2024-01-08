#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  5 01:19:53 2018
@author: Patrick
"""

import argparse
import codecs
import json
import os
import re
import ssl
import sys
import time
from copy import deepcopy
from functools import partial
from pprint import pprint
from urllib.request import URLError
from urllib.request import urlopen as _urlopen

from bs4 import BeautifulSoup
from tqdm import tqdm
import webcolors

from ebookmaker.ebookmaker import OPFGenerator

# for cover image:
try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as error:
    print(f'Warning: pillow not found. New cover image will not be generated. Error: {error}')

def distance_squared(a, b):
    return sum((x -y)**2 for x, y in zip(a, b))

def get_semantic_color_from_hex(hex, spec='css3'):
    if spec not in webcolors.SUPPORTED_SPECIFICATIONS:
        raise ValueError("Spec must be one of: {webcolors.SUPPORTED_SPECIFICATIONS}")
    semantic_color = "UNKNOWN"
    try:
        semantic_color = webcolors.hex_to_name(hex, spec)
    except ValueError:
        rgb = webcolors.hex_to_rgb(hex)
        mindist = 255**3
        for cvalue, cname in getattr(webcolors, f'{spec.upper()}_HEX_TO_NAMES').items():
            d = distance_squared(rgb, webcolors.hex_to_rgb(cvalue))
            if d < mindist:
                mindist = d
                semantic_color = cname
    return semantic_color


class RateLimited:
    """Simple wrapper class to delay arbitrary function calls for a specific time

    Attempting to avoid triggering IP ban for hitting website too quickly when scraping. Decrease
    time at your own risk.
    """

    def __init__(self, function, default_kwargs=None, limit=60):
        self.function = function
        self.default_kwargs = default_kwargs
        self.limit = limit # limit calls to 1x/min to try to avoid tripping IP ban
        self._last_called = 0 # no limit on first call

    def __call__(self, *args, **kwargs):
        next_call = self._last_called + self.limit
        delay = next_call - time.time()
        if 0 < delay:
            print(f'Delaying call to {self.function} for {delay} s due to limit {self.limit} s')
            time.sleep(delay)
        self._last_called = time.time()
        # append self.args/kwargs:
        if self.default_kwargs:
            for k, v in self.default_kwargs.items():
                if k in kwargs:
                    pass
                else:
                    kwargs[k] = v
        return self.function(*args, **kwargs)

    def set_limit(self, limit):
        if 0 <= limit:
            self.limit = limit


# Replace urlopen with a rate limited version after parsing relevant args
urlopen = None


class Chapter:
    _HTML_HEADER = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11\
    /DTD/xhtml11.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="author" content="pirate aba"/>
    <meta name="description" content="The Wandering Inn"/>
    <meta name="classification" content="Fantasy" />
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
            return urlopen(self.url)
        else:
            return urlopen('https://wanderinginn.com/' + self.url)

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
                    try:
                        hexcolor = re.findall(r'(?<=color\:)\#[0-9a-fA-F]{6}', str(span))[0]
                        color = get_semantic_color_from_hex(hexcolor).upper()
                    except Exception as error:
                        print(f'Error replacing color: {error}')
                        continue;
                    span.insert(0, f'<{color}|')
                    span.append(f'|{color}>')
                    span.unwrap() # bs4 method for replaceWithChildren

        # Download and replace image urls with local references:
        for img in contents.find_all('img'):
            img_filename = None
            try:
                img_filename = os.path.split(img['data-orig-file'])[1]
            except KeyError:
                try:
                    # data-orig-file not specified. Try using src end of path and stripping off any html params:
                    img_filename = os.path.split(img['src'])[1].partition('?')[0]
                except KeyError:
                    pass
            if img_filename:
                with open(os.path.join(image_path, img_filename), 'wb') as fo:
                    fo.write(urlopen(img['src'], timeout=10).read())
                img['src'] = os.path.join(image_path, img_filename)
            else:
                print(f'Removing image: unable to determine filename:\n\t{img}')

        title = page.find('h1', {'class': 'entry-title'}).text.strip()
        h1 = page.new_tag('h1', id=self.index)
        h1.string = title

        print(f'{Chapter._HTML_HEADER}\n{h1}\n{contents}\n\n</body>\n</html>\n',
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

    def __hash__(self):
        return hash((self.volume, self.index))



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir',
                        dest='build_dir',
                        default='./build',
                        help='Directory to build epubs',
                        )
    parser.add_argument('--strip-color',
                        dest='strip_color',
                        action='store_true',
                        help='If true, remove color information from text (e.g. for display on black-and-white devices)',
                        )
    parser.add_argument('--volume',
                        default=[],
                        type=int,
                        nargs='+',
                        help='Volume(s) to get for ebook (default: all; if chapter specified, default is None)',
                        )
    parser.add_argument('--chapter',
                        default=[],
                        nargs='+',
                        help='Chapter(s) to get for ebook (default: all; if volume specified, default is all in volume(s) specified))',
                        )
    parser.add_argument('--rate-limit',
                        dest='rate_limit',
                        type=int,
                        default=None,
                        help='Delay in seconds imposed between urlopen calls to prevent hitting site rate limit',
                        )
    parser.add_argument('--cafile', 
                        type=str,
                        default=None,
                        help='Default cafile to use w/ ssl (only use if getting ssl errors when using system CA)',
                        )

    # Default output: all content in a single book
    # Other options:
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument('--output-by-volume',
                              dest='by_volume',
                              action='store_true',
                              help='Generate one ebook per volume',
                              )
    output_group.add_argument('--output-by-chapter',
                              dest='by_chapter',
                              action='store_true',
                              help='Generate one ebook per chapter',
                              )
    output_group.add_argument('--output-print-index',
                              dest='print_index',
                              action='store_true',
                              help='Pretty-print the effective index (list of chapters) and exit (useful for testing volume/chapter selection)',
                              )
    output_group.add_argument('--output-title',
                              dest='title',
                              type=str,
                              default="The Wandering Inn",
                              help='Title to use for single-output file (default: "The Wandering Inn")',
                              )

    args = parser.parse_args()

    # Configure rate-limited urlopen:
    limiter_args = dict()
    urlopen_args = dict()
    urlopen_args['timeout'] = 5.0 # default urlopen timeout; overridden to 10.0 for images
    urlopen_args['context'] = ssl.create_default_context()
    limiter_args['default_kwargs'] = urlopen_args
    if args.rate_limit:
        limiter_args['limit'] = args.rate_limit
    if args.cafile:
        limiter_args['default_kwargs']['cafile'] = args.cafile
    global urlopen
    urlopen = RateLimited(_urlopen, **limiter_args)

    return args


def get_toc(toc_url=r'https://wanderinginn.com/table-of-contents/'):
    page = urlopen(toc_url)
    soup = BeautifulSoup(page, 'lxml')

    toc = []
    for volume_wrapper in soup.find_all('div', {'class': 'volume-wrapper'}):
        wrapper_id = volume_wrapper.get('id')
        try:
            volume = int(wrapper_id.replace("vol-","").strip())
        except ValueError:
            print(f"Unable to get volume from volume wrapper id: {wrapper_id}")
            continue

        for index, chapter_cell in enumerate(volume_wrapper.find_all('div', {'class': 'body-web table-cell'})):
            chapters = [Chapter(link['href'], link.text, volume, index + inner)
                        for inner, link in enumerate(chapter_cell.find_all('a', href=True))]
            if len(chapters) != 1:
                print(f"Unexpected results for chapter cell: {chapter_cell}, {chapters}")
            toc.extend(chapters)
    return toc 

def create_cover_image(base_image, title, subtitle=None, outdir=None):
    if outdir is None:
        outdir = os.path.split(base_image)[0]
    ext = os.path.splitext(base_image)[1]
    new_name = title.replace(' ', '_')
    if subtitle:
        new_name = f'{new_name}_{subtitle.replace(" ", "_")}'
    new_image = os.path.join(outdir, new_name + ext)
    color = (255, 255, 60) # yellow
    fontname = 'font/RobotoSlab-VariableFont_wght.ttf'
    pad = 15
    try:
        with Image.open(base_image) as image:
            editable = ImageDraw.Draw(image)
            title_font = ImageFont.truetype(fontname, 40)
            editable.text((pad, pad + title_font.getsize(title)[1]), title, color, font=title_font)
            if subtitle:
                subtitle_font = ImageFont.truetype(fontname, 30)
                height = pad + title_font.getsize(title)[1] + pad + subtitle_font.getsize(subtitle)[1]
                editable.text((pad, height), subtitle, color, font=subtitle_font)
            os.makedirs(outdir, exist_ok=True)
            image.save(new_image)
    except Exception as error:
        print(f'Unable to create cover image for {title}: {error}')
        new_image = base_image
    return new_image


def get_book(ebook_data,
             volume=None,
             index=None,
             chapter=None,
             strip_color=False,
             build_dir='./build',
             title='The Wandering Inn',
             subtitle=None,
             ):

    if index is None:
        index = get_toc()

    if chapter is not None:
        #subtitle = f'Volume {chapter.volume:02d}.{chapter.index:03d} - Chapter {chapter.name}'
        subtitle = f'Volume {chapter.volume}.{chapter.index:03d} - Chapter {chapter.name}'
    elif volume is not None:
        subtitle = f'Volume {volume}'

    html_path = os.path.join(build_dir, 'html')
    image_path = os.path.join(html_path, 'images')
    os.makedirs(html_path, exist_ok=True)
    os.makedirs(image_path, exist_ok=True)

    cover_path = os.path.join(build_dir, 'covers')
    ebook_data['cover'] = create_cover_image(ebook_data['cover'], title, subtitle, outdir=cover_path)
    ebook_data['title'] = title
    if subtitle:
        ebook_data['title'] = f'{title} - {subtitle}'

    def include_chapter(ch):
        return (volume is None or ch.volume == volume) and (chapter is None or ch == chapter)

    for ch in tqdm(list(filter(include_chapter, index)), "Chapter"):
        filename = os.path.join(html_path, ch.filename)
        ebook_data['contents'].append({'generate': False, 'type': 'text', 'source': filename})
        if not os.path.isfile(filename):
            try:
                with codecs.open(filename, 'w', encoding='utf-8') as fh:
                    ch.save(stream=fh, strip_color=strip_color, image_path=image_path)
            except URLError as err:
                os.unlink(filename)
                raise err


def main():
    args = parse_args()

    with open('the_wandering_inn.json') as fh:
        ebook_data = json.load(fh)

    full_toc = get_toc()

    # trim the full_toc to only chapters that should be included
    # By default, everything is included
    # If user passed either volume or chapter arguments, include only the specified volume(s) and
    # chapter(s) (e.g., if volume == [1, 3] and chapter == 'latest', include all chapters that are
    # in volume 1 or 3 and the latest published chapter)
    toc = []
    if not args.chapter and not args.volume:
        index = full_toc
        args.volume = sorted(set((c.volume for c in index)))
    else:
        chapters = set()
        for chapter_title in args.chapter:
            if chapter_title == 'latest':
                chapters.add(full_toc[-1])
            else:
                try:
                    chapters.add([c for c in full_toc if c.name == chapter_title][-1])
                except Exception as error:
                    print(f'Unable to find matching chapter for {chapter_title}: {error}')
        if args.chapter and not chapters:
            raise Exception('No listed chapters were found!')
        if args.volume:
            for c in full_toc:
                if c.volume in args.volume:
                    chapters.add(c)
        index = sorted(list(chapters))

    if args.print_index:
        pprint(index)
        return

    if args.by_chapter:
        for chapter in tqdm(index):
            chapter_data = deepcopy(ebook_data)
            get_book(chapter_data,
                     chapter=chapter,
                     index=[chapter],
                     build_dir=args.build_dir,
                     strip_color=args.strip_color,
                     )
            gen = OPFGenerator(chapter_data)
            gen.createEBookFile(os.path.join(args.build_dir, f'{chapter_data["title"]}.epub'))
    elif args.by_volume:
        for volume in tqdm(args.volume, "Volume"):
            volume_data = deepcopy(ebook_data)
            get_book(volume_data,
                     volume=volume,
                     index=filter(lambda c: c.volume == volume, index),
                     build_dir=args.build_dir,
                     strip_color=args.strip_color,
                     )
            gen = OPFGenerator(volume_data)
            gen.createEBookFile(os.path.join(args.build_dir, f'{volume_data["title"]}.epub'))
    else:
        get_book(ebook_data,
                index=index,
                build_dir=args.build_dir,
                title=args.title,
                strip_color=args.strip_color,
                )
        gen = OPFGenerator(ebook_data)
        gen.createEBookFile(os.path.join(args.build_dir, f'{ebook_data["title"]}.epub'))

if __name__ == "__main__":
    main()
