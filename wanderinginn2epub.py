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
import sys
import re
import warnings
import time
from copy import deepcopy
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
    warnings.warn(f'Warning: pillow not found. New cover image will not be generated. Error: {error}')

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

    def __init__(self, function, limit=60):
        self.function = function
        self.limit = limit # limit calls to 1x/min to try to avoid tripping IP ban
        self._last_called = 0 # no limit on first call

    def __call__(self, *args, **kwargs):
        next_call = self._last_called + self.limit
        delay = next_call - time.time()
        if 0 < delay:
            time.sleep(delay)
        self._last_called = time.time()
        return self.function(*args, **kwargs)

    def set_limit(self, limit):
        if 0 <= limit:
            self.limit = limit


# Replace urlopen with a rate limited version:
urlopen = RateLimited(_urlopen)


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
</body>
</html>
'''

    def __init__(self, url, link_text='', volume=0, index=0, cache_dir=None):
        self.url = url
        self.name = link_text
        self.volume = volume
        self.index = index
        if self.name == 'Glossary':
            self.volume = 999999
            self.index  = 999999
        self.filename = f'wandering_inn-{self.volume:02d}.{self.index:03d}-{self.name}.html'
        self.cache_dir = cache_dir
        self.page = None

    def download_images(self, image_dir='./images'):
        # Download and replace image urls with local references:
        for img in self.page.find_all('img'):
            img_filename = None
            try:
                img_filename = os.path.split(img['data-orig-file'])[1].partition('?')[0]
            except KeyError:
                try:
                    # data-orig-file not specified. Try using src end of path and stripping off any html params:
                    img_filename = os.path.split(img['src'])[1].partition('?')[0]
                except KeyError:
                    pass
            if img_filename:
                if not os.path.isfile(img_filename):
                    with open(os.path.join(image_dir, img_filename), 'wb') as fo:
                        fo.write(urlopen(img['src'], timeout=5).read())
                img['src'] = os.path.join(image_dir, img_filename)
            else:
                warnings.warn(f'Removing image: unable to determine filename:\n\t{img}')

    def strip_images(self):
        for img in self.page.find_all('img'):
            img_template = '<img: {}>'
            img_text = 'UNKNOWN'
            try:
                img_text = img['alt']
            except KeyError:
                try:
                    image_text = os.path.split(img['src'])[1].partition('?')[0]
                except KeyError:
                    pass
                except IndexError:
                    pass
            img.replace_with(img_template.format(img_text))

    def strip_color(self):
        # Strip color from text that can make it hard to read on a paperwhite:
        for span in self.page.find_all('span'):
            if 'color' in str(span):
                try:
                    hexcolor = re.findall(r'(?<=color\:)\#[0-9a-fA-F]{6}', str(span))[0]
                    color = get_semantic_color_from_hex(hexcolor).upper()
                except Exception as error:
                    warnings.warn(f'Error replacing color: {error}')
                    continue;
                span.insert(0, f'<{color}| ')
                span.append(f' |{color}>')
                span.unwrap() # bs4 method for replaceWithChildren

    def fetch_page(self):
        '''Download content and extract chapter from page'''
        try:
            page = BeautifulSoup(urlopen(self.url, timeout=5), 'lxml')
        except URLError as err:
            warnings.warn(f'Unable to open {self}')
            raise err

        contents = page.find('div', {'class': 'entry-content'})
        end_content = contents.find('hr')

        # Strip everything after the <hr> block (links to next/previous pages, comments, etc):
        if end_content:
            [s.decompose() for s in end_content.find_next_siblings()]
            end_content.decompose()

        # Attempt to strip the author's note:
        author_note = [p for p in contents.find_all('p') if p.getText()[0:6] == 'Author' and 'Note' in p.getText()[0:13]]
        if author_note:
            end_content = author_note[0]
            [s.decompose() for s in end_content.find_next_siblings()]
            end_content.decompose()

        # Generate a page with appropriate headers and add the contents:
        self.page = BeautifulSoup(self._HTML_HEADER, 'lxml')
        self.page.find_all('body')[0].append(contents)

    def cache(self):
        """Download and save page entry-content"""

        if self.cache_dir is None:
            raise ValueError('Unable to cache page with self.cache_dir of None')

        # do not rely on self.page being correct, since it could have been modified: always fetch
        # content when directly calling cache:
        self.fetch_page()

        with open(os.path.join(self.cache_dir, self.filename), 'w') as fout:
            # Write the cached page:
            print(self.page, file=fout)

    def load_cache(self, force_reload=False):
        '''Load a cached chapter page'''
        if not self.cache_dir:
            return False
        if not force_reload and self.page and self.page.text:
            return True
        cache_file = os.path.join(self.cache_dir, self.filename)
        if os.path.isfile(cache_file):
            with open(cache_file, 'r') as fh:
                self.page = BeautifulSoup(fh.read(), 'lxml')
            if not self.page or not self.page.text:
                self.page = None
        return self.page is not None

    def generate_ebook_html(self,
                            html_dir,
                            chapter_level=1,
                            volume_level=None,
                            strip_color=False,
                            image_dir='./images',
                            ):
        if image_dir:
            self.download_images()
        else:
            self.strip_images()

        if strip_color:
            self.strip_color()

        h1 = self.page.find('h1')
        if not h1:
            h1 = self.page.new_tag('h1')
            self.page.find('head').append(h1)
        h1['id'] = self.index
        h1.string = self.name

        if volume_level in range(1, 7):
            if self.index == 0:
                v1 = self.page.new_tag(f'h{volume_level}', id=f'v{self.volume}')
                v1.string = f'Volume {self.volume}'
                h1.insert_before(v1)

        if chapter_level != 1 and chapter_level in range(1, 7):
            ch = self.page.new_tag(f'h{chapter_level}', id=self.index)
            ch.string = self.name
            h1.replace_with(ch)
        elif chapter_level is None:
            h1.decompose()

        filename = os.path.join(html_dir, self.filename)
        with codecs.open(filename, 'w', encoding='utf-8') as fh:
            print(self.page, file=fh)
        return filename

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


class DeprecateIndex(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        warnings.warn('Argument "--output-print-index" is deprecated; use "--output-print-toc" instead.')
        setattr(namespace, self.dest, True)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir',
                        dest='cache_dir',
                        default='./cache',
                        help='Directory to cache html',
                        )
    parser.add_argument('--build-dir',
                        dest='build_dir',
                        default='./build',
                        help='Directory to build epubs',
                        )
    parser.add_argument('--image-dir',
                        dest='image_dir',
                        default=None,
                        help='Directory to download images for local cache. Default is none (remove images)',
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
    parser.add_argument('--chapter-level',
                        default=1,
                        help='Heading level (html) to use for chapter(s) (default: 1; 1-6 allowed)',
                        )
    parser.add_argument('--volume-level',
                        default=1,
                        help='Heading level (html) to use for volume(s) (default: None; 1-6 allowed)',
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
    output_group.add_argument('--output-print-toc',
                              dest='print_toc',
                              action='store_true',
                              help='Pretty-print the effective index (list of chapters) and exit (useful for testing volume/chapter selection)',
                              )
    output_group.add_argument('--output-title',
                              dest='title',
                              type=str,
                              default="The Wandering Inn",
                              help='Title to use for single-output file (default: "The Wandering Inn")',
                              )

    # Deprecated arguments:
    output_group.add_argument('--output-print-index',
                              dest='print_toc',
                              action=DeprecateIndex,
                              help='Deprecated; use --output-print-toc instead',
                              )

    args = parser.parse_args()
    return args


def get_toc(toc_url=r'https://wanderinginn.com/table-of-contents/'):
    page = urlopen(toc_url)
    soup = BeautifulSoup(page, 'lxml').find('div', {'class': 'entry-content'})
    paragraphs = soup.find_all('p')

    toc = []
    volume = 0
    for v, chapters in zip(paragraphs[1::2], paragraphs[2::2]):
        try:
            volume = int(v.text.replace("Volume","").strip())
        except ValueError:
            warnings.warn(f"Unable to get volume from text: {v}")
        toc.extend([Chapter(link['href'], link.text, volume, index) for index, link in enumerate(chapters.find_all('a', href=True))])
    return toc

# hacky way to write toc for testing with project gutenberg's ebookmaker; not currently used
def write_toc(toc, fh):
    fh.write(toc[0]._HTML_HEADER)
    for c in toc:
        fh.write(f'<h1><a href="{c.filename}">{c.name}</a></h1>\n')
    fh.write('</body>\n</html>')

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
        warnings.warn(f'Unable to create cover image for {title}: {error}')
        new_image = base_image
    return new_image


def get_book(ebook_data,
             volume=None,
             toc=None,
             chapter=None,
             strip_color=False,
             build_dir='./build',
             cache_dir='./cache',
             image_dir=None,
             title='The Wandering Inn',
             subtitle=None,
             chapter_level=1,
             volume_level=None,
             index=None, # deprecated
             ):

    # Handle deprecated arguments:
    if index is not None:
        warnings.warn('Use of kwarg "index" in "get_book" is deprecated; use "toc" instead.')
        if toc is None:
            toc = index
        else:
            warnings.warn('   "toc" also used. Ignoring "index"')

    if toc is None:
        toc = get_toc()

    if chapter is not None:
        subtitle = f'Volume {chapter.volume:02d}.{chapter.index:03d} - Chapter {chapter.name}'
        #subtitle = f'Volume {chapter.volume}.{chapter.index:03d} - Chapter {chapter.name}'
    elif volume is not None:
        subtitle = f'Volume {volume:02d}'

    html_dir = os.path.join(build_dir, 'html')
    os.makedirs(html_dir, exist_ok=True)

    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    if image_dir:
        os.makedirs(image_dir, exist_ok=True)

    cover_dir= os.path.join(build_dir, 'covers')
    ebook_data['cover'] = create_cover_image(ebook_data['cover'], title, subtitle, outdir=cover_dir)
    ebook_data['title'] = title
    if subtitle:
        ebook_data['title'] = f'{title} - {subtitle}'

    def include_chapter(ch):
        return (volume is None or ch.volume == volume) and (chapter is None or ch == chapter)

    for ch in tqdm(list(filter(include_chapter, toc)), "Chapter"):
        if cache_dir:
            ch.cache_dir = cache_dir
            if not ch.load_cache():
                ch.cache()
        else:
            ch.fetch_page()
        filename = ch.generate_ebook_html(html_dir,
                                          chapter_level=chapter_level,
                                          volume_level=volume_level,
                                          strip_color=strip_color,
                                          image_dir=image_dir,
                                          )
        ebook_data['contents'].append({'generate': False, 'type': 'text', 'source': filename})

def gen_toc_from_cache(cache_dir):

    chapters = os.listdir(cache_dir)
    toc = []
    for ch in chapters:
        url = os.path.join(cache_dir, ch)
        _, ch_v, *title = ch.split('-')
        title = '-'.join(title)
        if title.endswith('.html'):
            title = title[0:-5]
        volume, index = [int(x) for x in ch_v.split('.')]
        toc.append(Chapter(url, link_text=title, volume=volume, index=index, cache_dir=cache_dir))
    return toc

def main():
    args = parse_args()

    with open('the_wandering_inn.json') as fh:
        ebook_data = json.load(fh)

    try:
        full_toc = get_toc()
    except URLError as error:
        if args.cache_dir:
            warnings.warn('Unable to retrieve live toc; generating from cache')
            full_toc = gen_toc_from_cache(args.cache_dir)
        else:
            raise error

    # trim the full_toc to only chapters that should be included
    # By default, everything is included
    # If user passed either volume or chapter arguments, include only the specified volume(s) and
    # chapter(s) (e.g., if volume == [1, 3] and chapter == 'latest', include all chapters that are
    # in volume 1 or 3 and the latest published chapter)
    toc = []
    if not args.chapter and not args.volume:
        toc = full_toc
        args.volume = sorted(set((c.volume for c in toc)))
    else:
        chapters = set()
        for chapter_title in args.chapter:
            if chapter_title == 'latest':
                chapters.add(full_toc[-1])
            else:
                try:
                    chapters.add([c for c in full_toc if c.name == chapter_title][-1])
                except Exception as error:
                    warnings.warn(f'Unable to find matching chapter for {chapter_title}: {error}')
        if args.chapter and not chapters:
            raise Exception('No listed chapters were found!')
        if args.volume:
            for c in full_toc:
                if c.volume in args.volume:
                    chapters.add(c)
        toc = sorted(list(chapters))

    if args.print_toc:
        pprint(toc)
        return

    # ebookmaker isn't actively maintained to update to suppress warning; until I replace it,
    # suppress the warning from here instead:
    warnings.filterwarnings('ignore', category=UserWarning, module='ebookmaker', message="No parser was explicitly specified")

    if args.by_chapter:
        for chapter in tqdm(toc):
            chapter_data = deepcopy(ebook_data)
            get_book(chapter_data,
                     chapter=chapter,
                     toc=[chapter],
                     build_dir=args.build_dir,
                     cache_dir=args.cache_dir,
                     image_dir=args.image_dir,
                     strip_color=args.strip_color,
                     )
            gen = OPFGenerator(chapter_data)
            gen.createEBookFile(os.path.join(args.build_dir, f'{chapter_data["title"]}.epub'))
    elif args.by_volume:
        for volume in tqdm(args.volume, "Volume"):
            volume_data = deepcopy(ebook_data)
            get_book(volume_data,
                     volume=volume,
                     toc=filter(lambda c: c.volume == volume, toc),
                     build_dir=args.build_dir,
                     cache_dir=args.cache_dir,
                     image_dir=args.image_dir,
                     strip_color=args.strip_color,
                     )
            gen = OPFGenerator(volume_data)
            gen.createEBookFile(os.path.join(args.build_dir, f'{volume_data["title"]}.epub'))
    else:
        get_book(ebook_data,
                toc=toc,
                build_dir=args.build_dir,
                cache_dir=args.cache_dir,
                image_dir=args.image_dir,
                title=args.title,
                strip_color=args.strip_color,
                )
        gen = OPFGenerator(ebook_data)
        gen.createEBookFile(os.path.join(args.build_dir, f'{ebook_data["title"]}.epub'))

if __name__ == "__main__":
    main()
