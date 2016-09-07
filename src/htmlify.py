"""
Command-line utility (and module consisting of functions/methods) for
"HTMLifying" raw song lyrics text files accompanied by album/song
metadata and some other content, including images and homepage content.

Usage:

    ```htmlify```

        - Will generate all of the website pages.

    ```htmlify --make_downloads```

        - Will generate all of the website pages and also generate the
          lyrics downloads files, which contain collections of the raw
          lyrics files.
"""
import re
import sys
from math import ceil
from glob import glob
from itertools import chain
from os.path import join, getsize, exists
from string import ascii_uppercase

import cytoolz
from bs4.element import Tag
from bs4 import BeautifulSoup
from markdown import Markdown
from typing import Dict, List, Optional, Tuple
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from src import (Album, Song, SongFilesDictType, file_id_types_to_skip,
                 root_dir_path, albums_dir, songs_dir, resources_dir,
                 images_dir, albums_index_html_file_name, downloads_file_name,
                 all_songs_with_metadata_file_name, all_songs_file_name,
                 all_songs_unique_file_name, text_dir_path,
                 song_index_dir_path, songs_and_albums_index_json_file_path,
                 songs_index_html_file_path, album_index_dir_path,
                 albums_index_html_file_path, file_dumps_dir_path,
                 main_index_html_file_path, home_page_content_file_path,
                 ANNOTATION_MARK_RE, remove_inline_annotation_marks,
                 generate_lyrics_download_files, and_join_album_links,
                 sort_titles, read_songs_index, remove_annotations,
                 standardize_quotes, clean_up_html, prepare_html,
                 find_annotation_indices, add_html_declaration,
                 make_head_element, make_navbar_element)


def generate_index_page(albums: List[Album]) -> None:
    """
    Generate the main site's index.html page.

    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None
    """

    html = Tag(name='html')
    
    # Add in head element
    html.append(make_head_element(0))

    # Start to construct the body tag, including a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 0))

    # Add in home page content (introduction, contributions, etc.),
    # which is stored in a file in the resources directory called
    # "home_page_content.md" (as its name suggests it is in Markdown
    # format and therefore it will be necessary to convert
    # automatically from Markdown to HTML)
    markdowner = Markdown()
    with open(home_page_content_file_path) as home_markdown_file:
        home_page_content_html = \
            BeautifulSoup(markdowner.convert(home_markdown_file.read()),
                          'html.parser')
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    columns_div.append(home_page_content_html)
    row_div.append(columns_div)
    container_div.append(row_div)

    body.append(container_div)
    html.append(body)

    with open(main_index_html_file_path, 'w') as index_file:
        print(prepare_html(html), file=index_file, end='')


def generate_song_list_element(song: Song) -> Tag:
    """
    Make a list element for a song (for use when generating an album
    webpage, for example).

    :param song: Song object
    :type song: Song

    :returns: HTML list element
    :rtype: Tag
    """

    # Make a list element for the song
    li = Tag(name='li')
    sung_by = song.sung_by
    performed_by = song.written_and_performed_by.get('performed_by', '')
    written_by = song.written_by
    duet = song.duet
    live = song.live

    # If the song was sung by someone other than Bob Dylan, there will
    # be a "sung_by" key whose value will be the actual (and primary)
    # singer of the song, which should appear in a parenthetical
    # comment. If the song was originally written by someone other than
    # Bob Dylan or in partnership with Bob Dylan but the song is sung
    # by Bob Dylan (primarily, at least), then there will be a
    # "written_by" key that has this information. On the other hand, if
    # the song was both performed by someone other than Bob Dylan
    # (primarily, at least) and written by someone other than Bob Dylan
    # (primarily, again), then there will be a special
    # "written_and_performed_by" key.
    if sung_by:
        sung_by = ' (sung by {0})'.format(sung_by)
    elif performed_by:
        performed_by = ' (performed by {0})'.format(performed_by)

    # If the song was written by someone other than Bob Dylan or in
    # partnership with Bob Dylan, make a parenthetical comment for the
    # song's authorship
    if written_by:
        if written_by.startswith("Traditional"):
            written_by = ' ({})'.format(written_by)
        elif 'arranged by' in written_by:
            written_by = (' (originally written by {})'.format(written_by))
        else:
            authors = [author.strip() for author in written_by.split(",")]
            if len(authors) == 1:
                authors_string = authors[0]
            elif len(authors) == 2:
                authors_string = ' and '.join(authors)
            else:
                authors_string = ', and '.join([', '.join(authors[:-1]),
                                                authors[-1]])
            written_by = (' (original author{}: {})'
                          .format('s' if len(authors) > 1 else '',
                                  authors_string))

    # If the song is an instrumental, prepare a parenthetical comment
    # for that as well
    instrumental = ' (Instrumental)' if song.instrumental else ''

    # If the song was sung as a duet with somebody else, make a
    # parenthetical comment for that too
    if duet:
        duet = ' (duet with {})'.format(duet)

    # If the song was recorded live in concert, generate a
    # parenthetical comment
    if live:
        live = (' (recorded live {0} {1})'
                .format(live['date'], live['location/concert']))

    # Make a link for the song file if the song is not an instrumental
    # or was not performed by somebody else
    a_song = None
    if not instrumental and not performed_by:
        song_file_path = join('..', songs_dir, 'html',
                              '{0}.html'.format(song.file_id))
        a_song = Tag(name='a', attrs={'href': song_file_path})
        a_song.string = song.name

    if song.source:
        if not instrumental and not performed_by:

            li.append(a_song)

            # Construct the string content of the list element,
            # including the song name itself, a comment about the
            # song's original album, a comment about the song's
            # authorship if the list of authors includes someone other
            # than Bob Dylan, and a comment that the song was sung by
            # someone else or is basically just not a Bob Dylan song,
            # if either of those applies, etc.
            orig_album_file_path = join('..', albums_dir,
                                        '{0}'.format(song.source.get('file_id')))
            a_orig_album = Tag(name='a', attrs={'href': orig_album_file_path})
            a_orig_album.string = song.source.get('name')
            a_orig_album.string.wrap(Tag(name='i'))
            comment = Tag(name='comment')
            comment.string = (' (appeared on {0}{1}){2}{3}{4}'
                              .format(a_orig_album,
                                      sung_by,
                                      written_by,
                                      duet,
                                      live))
            li.append(comment)

        else:

            # Add in grayed-out and italicized song name
            i_song = Tag(name='i')
            gray = Tag(name='font', attrs={'color': '#726E6D'})
            gray.string = song.name
            i_song.append(gray)
            li.append(i_song)

            # Construct the string content of the list element,
            # including the song name itself, a comment that the song
            # is an instrumental song if that applies, a comment about
            # the song's authorship if the list of authors includes
            # someone other than Bob Dylan, and a comment that the song
            # was sung by someone else or is basically just not a Bob
            # Dylan song, if either of those applies, etc.
            comment = Tag(name='comment')
            comment.string = '{0}{1}{2}{3}{4}{5}'.format(instrumental,
                                                         sung_by,
                                                         performed_by,
                                                         written_by,
                                                         duet,
                                                         live)
            comment.string.wrap(Tag(name='i'))
            comment.string.wrap(Tag(name='font', attrs={'color': '#726E6D'}))
            li.append(comment)

    else:

        # If the song isn't an instrumental and there is an associated
        # lyrics file, then just add the a-tag for the song into the
        # list element; otherwise, gray out and italicize the text of
        # the song name
        if not instrumental and not performed_by:
            
            li.append(a_song)
            
            # Construct the string content of the list element,
            # including the song name itself, a comment that the song
            # is an instrumental song if that applies, a comment about
            # the song's authorship if the list of authors includes
            # someone other than Bob Dylan, and a comment that the song
            # was sung by someone else or is basically just not a Bob
            # Dylan song, if either of those applies, etc.
            comment = Tag(name='comment')
            comment.string = '{0}{1}{2}{3}{4}{5}'.format(instrumental,
                                                         sung_by,
                                                         performed_by,
                                                         written_by,
                                                         duet,
                                                         live)

        else:

            # Add in grayed-out and italicized song name
            i_song = Tag(name='i')
            gray = Tag(name='font', attrs={'color': '#726E6D'})
            gray.string = song.name
            i_song.append(gray)
            li.append(i_song)

            # Construct the string content of the list element,
            # including the song name itself, a comment that the song
            # is an instrumental song if that applies, a comment about
            # the song's authorship if the list of authors includes
            # someone other than Bob Dylan, and a comment that the song
            # was sung by someone else or is basically just not a Bob
            # Dylan song, if either of those applies, etc.
            comment = Tag(name='comment')
            comment.string = '{0}{1}{2}{3}{4}{5}'.format(instrumental,
                                                         sung_by,
                                                         performed_by,
                                                         written_by,
                                                         duet,
                                                         live)
            comment.string.wrap(Tag(name='i'))
            comment.string.wrap(Tag(name='font', attrs={'color': '#726E6D'}))

        li.append(comment)

    return li


def generate_song_list(songs: List[Song],
                       sides: Optional[Dict[str, str]] = None,
                       discs: Optional[Dict[str, str]] = None) -> Tag:
    """
    Generate an HTML element representing an ordered list of songs.

    If `sides_dict` or `discs_dict` is specified, use this information
    to break up the list of songs into sections.

    :param songs: list of Song objects
    :type songs: List[Song]
    :param sides: dictionary mapping side indices to song index ranges,
                  i.e., "1" -> "1-5"
    :type sides: Optional[Dict[str, str]]
    :param discs: dictionary mapping disc indices to song index ranges,
                  i.e., "1" -> "1-5"
    :type discs: Optional[Dict[str, str]]

    :returns: ordered list element
    :rtype: Tag

    :raises: ValueError if both `sides` and `discs` are specified or if
             either of the two conflict with assumptions
    """

    if sides and discs:
        raise ValueError('Only one of the following keyword arguments can be '
                         'passed in at a given time: `sides_dict` and '
                         '`discs_dict`.')

    columns_div = Tag(name='div', attrs={'class': 'col-md-8'})
    ol = Tag(name='ol')
    sections = sides or discs
    if sections:

        section_str = 'Side' if sides else 'Disc'

        # Iterate over the sides/discs, treating them as integers
        # (rather than strings)
        for section in sorted(sections, key=int):

            # Make sure the side/disc is interpretable as an integer
            try:
                if int(section) < 1:
                    raise ValueError
            except ValueError:
                raise ValueError('Each side/disc ID should be interpretable as'
                                 ' an integer that is greater than zero. '
                                 'Offending side/disc ID: "{0}".'
                                 .format(section))

            section_div = Tag(name='div')
            section_div.string = "{0} {1}".format(section_str, section)
            ol.append(section_div)
            ol.append(Tag(name='p'))
            inner_ol = Tag(name='ol')

            # Each side/disc will have an associated range of song
            # indices, e.g. "1-5" (unless a side/disc contains only a
            # single song, in which case it will simply be the song
            # index by itself)
            if '-' in sections[section]:
                first, last = sections[section].split('-')
                try:
                    if int(first) < 1:
                        raise ValueError
                    if int(last) < 1:
                        raise ValueError
                    if int(last) <= int(first):
                        raise ValueError
                except ValueError:
                    raise ValueError("Each side's/disc's associated range "
                                     "should consist of integer values greater"
                                     " than zero and the second value should "
                                     "be greater than the first. Offending "
                                     "range: \"{0}\"."
                                     .format(sections[section]))
            else:
                first = last = sections[section]
                try:
                    if int(first) < 1:
                        raise ValueError
                except ValueError:
                    raise ValueError("Each side's/disc's associated range can "
                                     "consist of a single value, but that "
                                     "value should be an integer greater than "
                                     "zero. Offending range: \"{0}\"."
                                     .format(sections[section]))

            # Get the expected number of songs for the given side/disc
            expected_number_of_songs = int(last) - int(first) + 1
            added_songs = 0
            for index, song in enumerate(songs):
                try:
                    if index + 1 in range(int(first), int(last) + 1):
                        inner_ol.append(generate_song_list_element(song))
                        added_songs += 1
                    if int(last) == index + 1:
                        break
                except TypeError:
                    raise ValueError('The "sides"/"discs" attribute contains '
                                     'invalid song indices: {0}.'
                                     .format(sections[section]))

            # Make sure the correct number of songs were included
            if added_songs != expected_number_of_songs:
                print('The number of expected songs ({0}) for the given '
                      'side/disc ({1}) does not equal the number of songs '
                      'actually included on the side/disc ({2}).'
                      .format(expected_number_of_songs, section, added_songs),
                      file=sys.stderr)

            ol.append(inner_ol)
            ol.append(Tag(name='p'))
    else:
        [ol.append(generate_song_list_element(song)) for song in songs]

    columns_div.append(ol)
    
    return columns_div


def htmlify_everything(albums: List[Album],
                       song_files_dict: SongFilesDictType,
                       make_downloads: bool = False,
                       allow_file_not_found_error: bool = False) -> Optional[List[Tuple[str, str, str]]]:
    """
    Create HTML files for the main index page, each album's index page,
    and the pages for all songs and, optionally, return a list of song
    name/album name/lyrics tuples.

    :param albums: list of Album objects
    :type albums: List[Album]
    :param song_files_dict: dictionary mapping song names to lists of
                            versions
    :type song_files_dict: dict
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool
    :param allow_file_not_found_error: skip songs after encountering
                                       one that does not exist ye
    :type allow_file_not_found_error: bool

    :returns: None or list of song nane/album name/lyrics tuples
    :rtype: Optional[List[Tuple[str, str, str]]]
    """

    # Generate index page for albums
    print('HTMLifying the albums index page...', file=sys.stderr)

    # Make HTML element for albums index page
    index_html = Tag(name='html')
    index_body = Tag(name='body')

    # Add in elements for the heading
    index_heading = Tag(name='h1')
    index_heading.string = 'Albums'
    index_heading.string.wrap(Tag(name='a',
                                  attrs={'href': albums_index_html_file_name}))
    index_body.append(index_heading)

    # Add in ordered list element for all albums
    index_ol = Tag(name='ol')
    for album in albums:
        album_html_file_name = '{}.html'.format(album.file_id)
        album_html_file_path = join(albums_dir, album_html_file_name)
        year = album.release_date.split()[-1]
        li = Tag(name='li')
        li.string = '{0} ({1})'.format(album.name, year)
        li.string.wrap(Tag(name='a', attrs={'href': album_html_file_path}))
        index_ol.append(li)
    index_body.append(index_ol)

    # Put body in HTML element
    index_html.append(index_body)

    # Write new HTML file for albums index page
    with open(join(root_dir_path,
                   albums_index_html_file_name), 'w') as albums_index:
        print(add_html_declaration(index_html.prettify(formatter="html")),
              file=albums_index, end='')

    # Generate pages for albums
    print('HTMLifying the individual album pages...', file=sys.stderr)
    if make_downloads:
        song_texts = \
            [htmlify_album(album, albums, make_downloads=True,
                           allow_file_not_found_error=allow_file_not_found_error)
             for album in albums]
        song_texts = list(chain(*song_texts))
    else:
        [htmlify_album(album, albums,
                       allow_file_not_found_error=allow_file_not_found_error)
         for album in albums]

    # Generate the main song index page
    print('HTMLifying the main song index page...', file=sys.stderr)
    htmlify_main_song_index_page(song_files_dict, albums)

    # Generate the main album index page
    print('HTMLifying the main album index page...', file=sys.stderr)
    htmlify_main_album_index_page(albums)

    if make_downloads:
        return song_texts

    return


def htmlify_album(album: Album, albums: List[Album],
                  make_downloads: bool = False,
                  allow_file_not_found_error: bool = False) -> Optional[List[Tuple[str, str, str]]]:
    """
    Generate HTML pages for a particular album and its songs and,
    optionally, return a list of song name/album name/lyrics tuples.

    :param album: Album object
    :type name: Album
    :param albums: list of all Album objects
    :type albums: List[Album]
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool
    :param allow_file_not_found_error: skip songs after encountering
                                       one that does not exist ye
    :type allow_file_not_found_error: bool

    :returns: None or list of song name/album/lyrics tuples
    :rtype: Optional[List[Tuple[str, str, str]]]
    """

    print('HTMLifying index page for {}...'.format(album.name),
          file=sys.stderr)

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(1))

    # Generate body for albums page and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 1))

    # Create div tag for the "container"
    container_div = Tag(name='div', attrs={'class': 'container'})

    # Add in elements for the heading
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    heading = Tag(name='h1')
    heading.string = album.name
    columns_div.append(heading)
    row_div.append(columns_div)
    container_div.append(row_div)

    # Add in the album attributes, including a picture of the album
    row_div = Tag(name='div',
                  attrs={'class': 'row', 'style': 'padding-top:12px'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-4'})
    attrs_div = Tag(name='div')
    image_file_path = join('..', resources_dir, images_dir, album.image_file_name)
    image = Tag(name='img',
                attrs={'src': image_file_path,
                       'width': '300px',
                       'style': 'padding-bottom:10px'})
    attrs_div.append(image)
    release_div = Tag(name='div')
    release_div.string = 'Released: {0}'.format(album.release_date)
    release_div.string.wrap(Tag(name='comment'))
    attrs_div.append(release_div)
    length_div = Tag(name='div')
    length_div.string = 'Length: {0}'.format(album.length)
    length_div.string.wrap(Tag(name='comment'))
    attrs_div.append(length_div)
    producers_string = album.producers
    producers_string_template = \
        'Producer{0}: {1}'.format('' if len(producers_string.split(', ')) == 1
                                  else '(s)', '{0}')
    producers_div = Tag(name='div')
    producers_div.string = producers_string_template.format(producers_string)
    producers_div.string.wrap(Tag(name='comment'))
    attrs_div.append(producers_div)
    label_div = Tag(name='div')
    label_div.string = 'Label: {0}'.format(album.label)
    label_div.string.wrap(Tag(name='comment'))
    attrs_div.append(label_div)
    by_div = Tag(name='div')
    if album.with_:
        by_div.string = 'By Bob Dylan and {}'.format(album.with_)
    else:
        by_div.string = 'By Bob Dylan'
    by_div.string.wrap(Tag(name='comment'))
    attrs_div.append(by_div)
    live = album.live
    if live:
        live_div = Tag(name='div')
        live_div.string = ('Recorded live {0} {1}'
                           .format(live.get('date'), live.get('location/concert')))
        live_div.string.wrap(Tag(name='comment'))
        attrs_div.append(live_div)
    columns_div.append(attrs_div)
    row_div.append(columns_div)

    # Add in an ordered list element for all songs (or several ordered
    # lists for each side, disc, etc.)
    row_div.append(generate_song_list(album.songs, sides=album.sides,
                                      discs=album.discs))
    container_div.append(row_div)

    # Add content to body and put body in HTML element
    body.append(container_div)
    html.append(body)

    # Write new HTML file for albums index page
    album_file_path = join(root_dir_path, albums_dir,
                           '{}.html'.format(album.file_id))
    with open(album_file_path, 'w') as album_file:
        print(prepare_html(html), file=album_file, end='')

    # Generate HTML files for each song (unless a song is indicated as
    # having appeared on previous album(s) since this new instance of
    # the song will simply reuse the original lyrics file) and,
    # optionally, add song name/text tuples to the `song_lyrics_tuples`
    # list so that lyrics download files can be generated at the end of
    # processing
    if make_downloads:
        song_lyrics_tuples = []
    for song in album.songs:

        # HTMLify the song
        if (not song.instrumental and
            not song.source and
            not song.written_and_performed_by):
            try:
                htmlify_song(song, albums)
            except FileNotFoundError as e:
                if allow_file_not_found_error:
                    break
                raise e

        # Add song name/song text tuple to the `song_lyrics_tuples` list
        # for the lyrics download files
        if (make_downloads and
            not song.instrumental and
            not song.written_and_performed_by):

            input_path = join(root_dir_path, text_dir_path,
                              '{0}.txt'.format(song.file_id))
            with open(input_path) as song_file:
                song_text = \
                    remove_annotations(standardize_quotes(song_file.read())).strip()
                song_lyrics_tuples.append((song.name, album.name, song_text))

    if make_downloads:
        return song_lyrics_tuples

    return


def htmlify_song(song: Song, albums: List[Album]) -> None:
    """
    Read in a raw text file containing lyrics and output an HTML file
    (unless the song is an instrumental and contains no lyrics).

    :param song: Song object
    :type song: Song
    :param albums: list of all Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None

    :raises: FileNotFoundError if the song text file does not exist
    """

    file_id = song.file_id
    name = song.name
    print('HTMLifying {}...'.format(name), file=sys.stderr)

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(2))

    # Create a body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 2))

    # Make a tag for the name of the song
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h_tag = Tag(name='h1')
    h_tag.string = name
    columns_div.append(h_tag)
    row_div.append(columns_div)
    container_div.append(row_div)

    # Process lines from raw lyrics file into different paragraph
    # elements
    input_path = join(root_dir_path, text_dir_path, '{0}.txt'.format(file_id))
    if not exists(input_path):
        print("Song file does not exist yet: {}".format(input_path),
              file=sys.stderr)
        raise FileNotFoundError
    with open(input_path) as raw_song_lyrics_file:
        song_lines = \
            standardize_quotes(raw_song_lyrics_file.read()).strip().splitlines()
    paragraphs = []
    current_paragraph = []
    footnotes = []
    footnote_indices = []
    for line_ind, line in enumerate(song_lines):
        line = line.strip()
        if line:

            # If the line begins with an element that both starts with
            # and ends with two asterisks in a row, that means that it
            # is a footnote line
            split_line = line.split(' ', 1)
            if split_line[0].startswith('**') and split_line[0].endswith('**'):
                try:
                    footnote_indices.append(int(split_line[0].replace('*', '')))
                except ValueError:
                    raise ValueError('{} contains what appears to be a '
                                     'footnote line but it seems to not be '
                                     'formatted correctly: {}'.format(name, line))
                footnotes.append(split_line[1])
                continue
            current_paragraph.append(line)
            if len(song_lines) == line_ind + 1:
                paragraphs.append(current_paragraph)
                current_paragraph = []
        else:
            paragraphs.append(current_paragraph)
            current_paragraph = []

    # Make sure that the footnotes line up correctly in terms of
    # numbering
    if footnote_indices != list(range(1, len(footnotes) + 1)):
        raise ValueError('The footnote indices for {} do not seem to be '
                         'numbered correctly.'.format(name))

    # Add paragraph elements with sub-elements of type `div` to the
    # `body` element
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    annotation_nums = []
    for paragraph in paragraphs:
        paragraph_elem = Tag(name='p')
        for line_elem in paragraph:

            # Create new `div` element to store the line
            div = Tag(name='div')

            # Check if line has annotations
            annotations = ANNOTATION_MARK_RE.findall(line_elem)
            if annotations:

                # If there are multiple annotations on a single line,
                # raise an error since it is not supported currently
                if len(annotations) > 1:
                    raise ValueError('There are multiple annotations in a line'
                                     ' in {}.'.format(name))

                # Add the annotation number to the list of annotation
                # numbers for the entire song
                annotation_nums.extend([int(annotation.replace('*', ''))
                                        for annotation in annotations])

                # Get indices for the annotations in the given line
                annotation_inds = find_annotation_indices(line_elem, annotations)

                # Remove annotation marks from the line
                line_elem = remove_inline_annotation_marks(line_elem)

                # Copy the contents of the line (after removing the
                # annotations) into the `div` element
                div.string = line_elem

                # Iterate over the annotations, generating anchor
                # elements that link the annotation to the note at the
                # bottom of the page
                # NOTE: Despite the fact that the code below is set up
                # to deal with multiple annotations on a single line,
                # the situation where there are multiple annotations on
                # a single line actually presents difficulties that are
                # not currently dealt with correctly. Therefore,
                # multiple annotations on a single line will trigger an
                # error before this point, which means that the list of
                # annotations will always consist of only one
                # annotation. 
                for i, annotation_num in enumerate(annotations):
                    href = '#{0}'.format(annotation_num)
                    a = Tag(name='a', attrs={'href': href})
                    a.string = annotation_num
                    a.string.wrap(Tag(name='sup'))

                    # Insert the anchor element into the `div` element
                    # at the appropriate location
                    ind = annotation_inds[i]
                    if ind == len(div.string):
                        div.string.replace_with('{0}{1}'
                                                .format(div.string, str(a)))
                    else:
                        div.string.replace_with('{0}{1}{2}'
                                                .format(div.string[:ind], str(a),
                                                        div.string[ind:]))

                        # After putting annotations back into the
                        # contents of the `div`, the indices of the
                        # annotations afterwards will necessarily
                        # change as they will be pushed back by the
                        # length of the string that is being added
                        for j in range(len(annotation_inds)):
                            if j > i:
                                annotation_inds[j] += len(a.string)
            else:

                # Copy the contents of the line into the `div` element
                div.string = line_elem

            # Insert the `div` element into the paragraph element
            paragraph_elem.append(div)

        columns_div.append(paragraph_elem)

    # Make sure that the footnotes and annotations line up correctly
    if footnote_indices or annotation_nums:
        if footnote_indices != annotation_nums:
            raise ValueError('The footnotes and annotations in {} do not match'
                             ' up correctly.'.format(name))


    # Add in the footnotes section (if there are any)
    if footnotes:
        footnotes_section = Tag(name='p')

        # Iterate over the footnotes, assuming the the index of the
        # list matches the natural ordering of the footnotes
        for footnote_index, footnote in enumerate(footnotes):
            div = Tag(name='div')
            div.string = '\t{}'.format(footnote)
            div.string.wrap(Tag(name='small'))

            # Generate a named anchor element for the footnote
            a = Tag(name='a', attrs={'name': str(footnote_index + 1)})
            a.string = str(footnote_index + 1)
            a.string.wrap(Tag(name='sup'))
            div.small.insert_before(a)
            footnotes_section.append(div)

        # Insert footnotes section at the next index
        columns_div.append(footnotes_section)

    # Add content to body and put body in HTML element
    row_div.append(columns_div)
    container_div.append(row_div)
    body.append(container_div)
    html.append(body)

    # Write out "prettified" HTML to the output file
    html_output_path = join(songs_dir, 'html', '{0}.html'.format(file_id))
    with open(join(root_dir_path, html_output_path), 'w') as song_file:
        print(prepare_html(html), file=song_file, end='')


def htmlify_main_song_index_page(song_files_dict: SongFilesDictType,
                                 albums: List[Album]) -> None:
    """
    Generate the main song index HTML page.

    :param song_files_dict: dictionary mapping song names to lists of
                            versions
    :type song_files_dict: dict
    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None
    """

    print('HTMLifying the main songs index page...', file=sys.stderr)

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(2))

    # Create a body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 2))

    # Make a container div for the index
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h = Tag(name='h1')
    h.string = 'Songs Index'
    columns_div.append(h)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(Tag(name='p'))

    for letter in ascii_uppercase:

        # Attempt to generate the index page for the letter: if a value
        # of False is returned, it means that no index page could be
        # generated (no songs to index for the given letter) and,
        # therefore, that this letter should be skipped.
        if not htmlify_song_index_page(letter, song_files_dict, albums):
            print('Skipping generating an index page for {0} since no songs '
                  'could be found...'.format(letter))
            continue

        row_div = Tag(name='div', attrs={'class': 'row'})
        columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
        div = Tag(name='div')
        letter_tag = Tag(name='letter')
        a = Tag(name='a',
                attrs={'href': join('{0}.html'.format(letter.lower()))})
        a.string = letter
        bold = Tag(name='strong', attrs={'style': 'font-size: 125%;'})
        a.string.wrap(bold)
        letter_tag.append(a)
        div.append(letter_tag)
        columns_div.append(div)
        row_div.append(columns_div)
        container_div.append(row_div)

    body.append(container_div)
    html.append(body)

    with open(songs_index_html_file_path, 'w') as songs_index_file:
        print(prepare_html(html), file=songs_index_file, end='')


def htmlify_song_index_page(letter: str, song_files_dict: SongFilesDictType,
                            albums: List[Album]) -> None:
    """
    Generate a specific songs index page.

    :param letter: index letter
    :type letter: str
    :param song_files_dict: dictionary mapping song names to lists of
                            versions
    :type song_files_dict: dict
    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: boolean value indicating whether a page was generated or
              not (depending on whether or not there were any songs
              found that started with the given letter)
    :rtype: bool
    """

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(2))

    # Create body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 2))

    # Make a container div tag to store the content
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h = Tag(name='h1')
    h.string = letter
    columns_div.append(h)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(Tag(name='p'))

    not_dylan = 'not written by or not performed by Bob Dylan'
    no_songs = True
    for song in sort_titles(list(song_files_dict), letter):

        # If the program gets here, there are songs; if not, the value
        # will not change, i.e., it will be True
        no_songs = False

        # Get information about the song, such as the different
        # versions of the song, their file IDs, which albums they
        # occurred on, whether they were instrumentals, etc.
        song_info = song_files_dict[song]

        row_div = Tag(name='div', attrs={'class': 'row'})
        columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
        div = Tag(name='div')
        if len(song_info) == 1:
            song_info = cytoolz.first(song_info)
            album_links = and_join_album_links(song_info['album(s)'])

            if song_info['file_id'] in file_id_types_to_skip:
                instrumental_or_not_dylan = song_info['file_id']
                if instrumental_or_not_dylan != 'instrumental':
                    instrumental_or_not_dylan = not_dylan
                div.append(song)
                comment = Tag(name='comment')
                comment.string = (' ({0}, appeared on {1})'
                                  .format(instrumental_or_not_dylan,
                                          album_links))
                div.append(comment)
                row_div.append(div)
                columns_div.append(row_div)
            else:
                song_html_file_path = \
                    '../html/{0}.html'.format(song_info['file_id'])
                a_song = Tag(name='a', attrs={'href': song_html_file_path})
                a_song.string = song
                div.append(a_song)
                comment = Tag(name='comment')
                comment.string = ' (appeared on {0})'.format(album_links)
                div.append(comment)
        else:
            div.string = song
            columns_div.append(div)

            # Make an unordered list for the different versions of the
            # song
            ul = Tag(name='ul')
            for i, version_info in enumerate(song_info):
                li = Tag(name='li')

                # Add in instrumental entries (but with no link to the
                # song pages since they don't exist), but don't even
                # add in entries for the songs that have been deemed as
                # non-Dylan songs
                if version_info['file_id'] == 'instrumental':
                    album_links = and_join_album_links(version_info['album(s)'])
                    comment = Tag(name='comment')
                    comment.string = ('Instrumental version (appeared on {0})'
                                      .format(album_links))
                    li.append(comment)
                elif version_info['file_id'] == 'not_written_or_peformed_by_dylan':
                    continue
                else:
                    album_links = and_join_album_links(version_info['album(s)'])
                    href = '../html/{0}.html'.format(version_info['file_id'])
                    a = Tag(name='a', attrs={'href': href})
                    a.string = 'Version #{0}'.format(i + 1)
                    li.append(a)
                    comment = Tag(name='comment')
                    comment.string = ' (appeared on {0})'.format(album_links)
                    li.append(comment)
                ul.append(li)
            div.append(ul)
        row_div.append(div)
        columns_div.append(row_div)
        container_div.append(columns_div)

    if no_songs:
        return False

    body.append(container_div)
    html.append(body)

    song_letter_index_file_path = join(root_dir_path, song_index_dir_path,
                                       '{0}.html'.format(letter.lower()))
    with open(song_letter_index_file_path, 'w') as letter_index_file:
        print(prepare_html(html), file=letter_index_file, end='')

    return True


def htmlify_main_album_index_page(albums: List[Album]):
    """
    Generate the main album index HTML page.

    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None
    """

    print('HTMLifying the main albums index page...', file=sys.stderr)

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(2))

    # Create a body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 2))

    # Make a container div for the index
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h = Tag(name='h1')
    h.string = 'Albums Index'
    columns_div.append(h)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(Tag(name='p'))

    for letter in ascii_uppercase:

        # Attempt to generate the index page for the letter: if a value
        # of False is returned, it means that no index page could be
        # generated (no albums to index for the given letter) and,
        # therefore, that this letter should be skipped.
        if not htmlify_album_index_page(letter, albums):
            print('Skipping generating an index page for {0} since no albums '
                  'could be found...'.format(letter))
            continue

        row_div = Tag(name='div', attrs={'class': 'row'})
        columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
        div = Tag(name='div')
        letter_tag = Tag(name='letter')
        a = Tag(name='a',
                attrs={'href': join('{0}.html'.format(letter.lower()))})
        a.string = letter
        bold = Tag(name='strong', attrs={'style': 'font-size: 125%;'})
        a.string.wrap(bold)
        letter_tag.append(a)
        div.append(letter_tag)
        columns_div.append(div)
        row_div.append(columns_div)
        container_div.append(row_div)

    body.append(container_div)
    html.append(body)

    with open(albums_index_html_file_path, 'w') as albums_index_file:
        print(prepare_html(html), file=albums_index_file, end='')


def htmlify_album_index_page(letter: str, albums: List[Album]) -> None:
    """
    Generate a specific albums index page.

    :param letter: index letter
    :type letter: str
    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: boolean value indicating whether a page was generated or
              not (depending on whether or not there were any albums
              found that started with the given letter)
    :rtype: bool
    """

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = Tag(name='html')
    html.append(make_head_element(2))

    # Create body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 2))

    # Make a container div tag to store the content
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h = Tag(name='h1')
    h.string = letter
    columns_div.append(h)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(Tag(name='p'))

    no_albums = True
    for album_name in sort_titles([album.name for album in albums], letter):

        # If the program gets here, there are albums; if not, the value
        # will not change, i.e., it will be True
        no_albums = False

        # Get album metadata
        album = [album for album in albums if album.name == album_name][0]

        row_div = Tag(name='div', attrs={'class': 'row'})
        columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
        div = Tag(name='div')
        a_album = Tag(name='a',
                      attrs={'href': join('..',
                                          '{0}.html'.format(album.file_id))})
        a_album.string = '{0} '.format(album_name)
        div.append(a_album)
        comment = Tag(name='comment')
        comment.string = '({0})'.format(album.release_date.split()[-1])
        div.append(comment)
        row_div.append(div)
        columns_div.append(row_div)
        container_div.append(columns_div)

    if no_albums:
        return False

    body.append(container_div)
    html.append(body)

    album_letter_index_file_path = join(root_dir_path, album_index_dir_path,
                                        '{0}.html'.format(letter.lower()))
    with open(album_letter_index_file_path, 'w') as letter_index_file:
        print(prepare_html(html), file=letter_index_file, end='')

    return True


def htmlify_downloads_page(albums: List[Album]) -> None:
    """
    Generate the downloads page.

    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None
    """

    # Get the size of the files in KiB
    file_sizes_dict = {file_path: ceil(getsize(file_path)/1024) for file_path
                       in glob(join(file_dumps_dir_path, '*.txt'))}

    html = Tag(name='html')
    html.append(make_head_element(1))

    # Create body element and add in a navigation bar
    body = Tag(name='body')
    body.append(make_navbar_element(albums, 1))

    # Make a tag for download links
    container_div = Tag(name='div', attrs={'class': 'container'})
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    h3 = Tag(name='h3')
    h3.string = 'Lyrics File Downloads'
    columns_div.append(h3)
    last_album = albums[-1]
    last_album_a = Tag(name='a',
                       attrs={'href': join('..', albums_dir,
                                           '{0}.html'.format(last_album.file_id))})
    last_album_a.string = last_album.name
    i = Tag(name='i')
    i.append(last_album_a)
    ul = Tag(name='ul')
    for file_name in [all_songs_with_metadata_file_name, all_songs_file_name,
                      all_songs_unique_file_name]:
        if file_name == 'all_songs_with_metadata.txt':
            text = ('All songs in the order in which they appeared on released'
                    ' albums + metadata, including song names and album names')
        elif file_name == 'all_songs.txt':
            text = ('All songs in the order in which they appeared on released'
                    ' albums')
        elif file_name == 'all_songs_unique.txt':
            text = 'All unique songs'
        download_a = ('<a href={0} download>{0}</a>: {1} (up to and including '
                      '{2}) ({3} KiB)'
                      .format(file_name, text, clean_up_html(str(i)),
                              file_sizes_dict[join(file_dumps_dir_path,
                                                   file_name)]))
        li = Tag(name='li')
        li.string = download_a
        ul.append(li)
    columns_div.append(ul)
    row_div.append(columns_div)
    container_div.append(row_div)
    body.append(container_div)
    html.append(body)

    with open(join(file_dumps_dir_path,
                   downloads_file_name), 'w') as downloads_file:
        print(prepare_html(html), file=downloads_file, end='')


def main():
    parser = ArgumentParser(conflict_handler='resolve',
                            formatter_class=ArgumentDefaultsHelpFormatter,
                            description='Generates HTML files based largely '
                                        'on the contents of the '
                                        'albums_and_songs_index.jsonlines '
                                        'file and on the raw text files that '
                                        'contain the lyrics.')
    parser.add_argument('--make_downloads',
                        help='Generate download files containing all of the '
                             'lyrics (both all of the songs concatenated '
                             'together and all of the unique songs in the '
                             'order of their appearance).',
                        action='store_true',
                        default=False)
    parser.add_argument('--allow_file_not_found_error',
                        help='Don\'t fail if a song lyrics text file is not '
                             'found (useful if not all songs from an album '
                             'entry in the index file have been added yet, but'
                             ' you want to htmlify all of the songs that are '
                             'available).',
                        action='store_true',
                        default=False)
    args = parser.parse_args()

    # Read in contents of the albums_and_songs_index.jsonlines file,
    # constructing a dictionary of albums and the associated songs,
    # etc.
    print('Reading the albums_and_songs_index.jsonlines file and building up '
          'index of albums and songs...',
          file=sys.stderr)
    albums, song_files_dict = \
        read_songs_index(songs_and_albums_index_json_file_path)

    # Generate HTML files for the main index page, albums, songs, etc.
    # and write raw lyrics files (for downloading), if requested
    print('Generating HTML files for the main page, albums, songs, etc....',
          file=sys.stderr)
    generate_index_page(albums)
    allow_file_not_found_error = args.allow_file_not_found_error
    if args.make_downloads:
        print('Generating the lyrics download files...', file=sys.stderr)
        generate_lyrics_download_files(
            htmlify_everything(albums,
                               song_files_dict,
                               make_downloads=True,
                               allow_file_not_found_error=allow_file_not_found_error))
        htmlify_downloads_page(albums)
    else:
        htmlify_everything(albums, song_files_dict,
                           allow_file_not_found_error=allow_file_not_found_error)

    print('Program complete.', file=sys.stderr)


if __name__ == '__main__':
    main()
