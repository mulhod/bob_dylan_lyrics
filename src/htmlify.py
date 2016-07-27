import re
import sys
from math import ceil
from glob import glob
from json import loads
from string import ascii_uppercase
from collections import OrderedDict
from os.path import join, getsize

import cytoolz
from bs4.element import Tag
from bs4 import BeautifulSoup
from markdown import Markdown
from typing import Any, Dict, List, Iterable, Tuple, Optional
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from src import (Album, Song, SongFilesDictType, IndexDictType,
                 file_id_types_to_skip, root_dir_path, albums_dir, songs_dir,
                 resources_dir, images_dir, file_dumps_dir, song_index_dir,
                 album_index_dir, main_index_html_file_name,
                 song_index_html_file_name, album_index_html_file_name,
                 albums_index_html_file_name, custom_style_sheet_file_name,
                 downloads_file_name, all_songs_file_name,
                 all_songs_unique_file_name, text_dir_path,
                 song_index_dir_path, songs_and_albums_index_json_file_path,
                 songs_index_html_file_path, album_index_dir_path,
                 albums_index_html_file_path, file_dumps_dir_path,
                 main_index_html_file_path, home_page_content_file_path,
                 ANNOTATION_MARK_RE, remove_inline_annotation_marks,
                 replace_double_quotes, replace_single_quotes,
                 CLEANUP_REGEXES_DICT, clean_title, get_title_index_letter)


# Lists for collecting song texts (used to create lyrics download files
# at the end of the process)
song_texts = []
unique_song_texts = set()


def read_json_index_file(file_path: str) -> IndexDictType:
    """
    Read the albums/songs index file (JSON format), stripping out any
    comments.

    :param file_path: path to index JSON file
    :type file_path: str

    :returns: a list of dictionaries containing information about
              albums, song indices, etc.
    :rtype: IndexDictType
    """

    return loads('\n'.join([line for line in open(file_path)
                            if not line.startswith('#')]))


def read_songs_index(index_json_path: str) -> Tuple[List[Album], SongFilesDictType]:
    """
    Read albums_and_songs_index.jsonlines file and make dictionary
    representation.

    :param index_json_path: path to JSON file containing metadata
                            describing each album and the files
                            related to it/its songs (in JSON format)
    :type index_json_path: str

    :returns: a tuple consisting of 1) an ordered dictionary
              associating album names (str) to dictionaries containing
              metadata attributes and ordered song dictionaries, which,
              in turn, consist of song IDs (str) mapped to dictionaries
              of song metadata, and 2) a dictionary mapping song names
              to lists of dictionaries containing information about
              various versions of songs
    :rtype: Tuple[List[Album], SongFilesDictType]

    :raises: ValueError
    """

    albums = []
    for collection in read_json_index_file(index_json_path):

        if collection['type'] == 'album':

            albums.append(Album(collection['type'], collection['metadata']))

        elif collection['type'] == 'song':

            # Define the actions to take when an entry only contains a
            # single song (when this comes up eventually)
            # NOTE: Remember to deal with adding the lyrics of the song
            # in question to the list of song lyrics.
            pass

        else:
            raise ValueError('Encountered a JSON object whose "type" attribute'
                             ' is neither "album" nor "song".')

    if not albums:
        raise ValueError('No albums/song collections found in index file!')

    # Make a dictionary mapping song names to a list of song versions
    # (file IDs, original album, etc.) for use in building the song
    # index
    song_files_dict = {}
    for album in albums:
        for song in album.songs:

            # Get the name of the song (some songs show up under
            # slightly different names on different albums or show up
            # more than once on a single album and thus require a
            # different key)
            song_name = song.actual_name if song.actual_name else song.name

            # Add in song name/file ID and album name/file ID to
            # `song_files_dict` (for the song index), indicating if the
            # song is an instrumental or if it wouldn't be associated
            # with an actual file ID for some other reason
            if song.instrumental:
                song_file_id = 'instrumental'
            elif song.written_and_performed_by:
                song_file_id = 'not_written_or_peformed_by_dylan'
            else:
                song_file_id = song.file_id

            file_album_dict = {'name': album.name, 'file_id': album.file_id}
            if song_name not in song_files_dict:
                song_files_dict[song_name] = [{'file_id': song_file_id,
                                               'album(s)': [file_album_dict]}]
            else:

                # Iterate over the entries in `song_files_dict` for a
                # given song, each entry corresponding to a different
                # `file_id` (basically, a different version of the same
                # song) and, if an entry for the song's file ID is
                # found, add its album to the list of albums associated
                # with that file ID/version, and, if not, then add the
                # file ID/version to the list of versions associated
                # with the song (i.e., with its own list of albums)
                found_file_id_in_song_dicts = False
                if song_file_id not in file_id_types_to_skip:
                    for file_ids_dict in song_files_dict[song_name]:
                        if file_ids_dict['file_id'] == song_file_id:
                            file_ids_dict['album(s)'].append(file_album_dict)
                            found_file_id_in_song_dicts = True
                            break
                if not found_file_id_in_song_dicts:
                    song_files_dict[song_name].append({'file_id': song_file_id,
                                                       'album(s)': [file_album_dict]})

    return albums, song_files_dict


def add_declaration(html_string: str) -> str:
    """
    Add in the declaration, i.e., "<!DOCTYPE html>", to the beginning
    of a string representation of an HTML file and return the new
    string.

    :param html_string: 
    :type html_string: str

    :returns: HTML string
    :rtype: str
    """

    return str(BeautifulSoup('<!DOCTYPE html>\n{0}'.format(html_string),
                             'html.parser'))


def make_head_element(level: int = 0) -> Tag:
    """
    Make a head element including stylesheets, Javascript, etc.

    :param level: number of levels down (from the root) the file for
                  which this head element will be used is located, if
                  any
    :type level: int

    :returns: HTML head element
    :rtype: Tag
    """

    head = Tag(name='head')
    head.append(Tag(name='meta', attrs={'charset': "utf-8"}))
    meta_tag = Tag(name='meta',
                   attrs={'name': 'viewport',
                          'content': 'width=device-width, initial-scale=1'})
    head.append(meta_tag)
    head.append(Tag(name='link',
                    attrs={'rel': 'stylesheet',
                           'href': 'http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css'}))
    head.append(Tag(name='link',
                    attrs={'rel': 'stylesheet',
                           'href': join(*['..']*level, resources_dir,
                                        custom_style_sheet_file_name)}))
    head.append(Tag(name='script',
                    attrs={'src': 'https://ajax.googleapis.com/ajax/libs/jquery/1.11.3/jquery.min.js'}))
    head.append(Tag(name='script',
                    attrs={'src': 'http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js'}))
    head.append(Tag(name='script',
                    attrs={'src': join(*['..']*level, resources_dir,
                                       'search.js')}))
    head.append(Tag(name='script',
                    attrs={'src': join(*['..']*level, resources_dir,
                                       'analytics.js')}))

    return head


def make_navbar_element(albums: List[Album], level: int = 0) -> Tag:
    """
    Generate a navigation bar element to insert into webpages for
    songs, albums, etc.

    :param albums: list of Album objects
    :type albums: List[Album]
    :param level: number of levels down (from the root) the file for
                  which this navigation bar will be used is located, if
                  any
    :type level: int

    :returns: HTML head element
    :rtype: Tag
    """

    up_levels = join('', *['..']*level)

    # Create a navigation element in which to put in buttons and
    # dropdown menus, etc.
    top_level_nav = Tag(name='nav', attrs={'class': 'navbar navbar-default'})
    container_div = Tag(name='div', attrs={'class': 'container-fluid'})
    navbar_header_div = Tag(name='div', attrs={'class': 'navbar-header'})
    navbar_collapse_button = Tag(name='button',
                                 attrs={'type': 'button',
                                        'class': 'navbar-toggle collapsed',
                                        'data-toggle': 'collapse',
                                        'data-target': '#bs-example-navbar-collapse-1',
                                        'aria-expanded': 'false'})
    button_span1 = Tag(name='span', attrs={'class': 'sr-only'})
    button_span1.string = 'Toggle navigation'
    button_span2 = Tag(name='span', attrs={'class': 'icon-bar'})
    button_span3 = Tag(name='span', attrs={'class': 'icon-bar'})
    button_span4 = Tag(name='span', attrs={'class': 'icon-bar'})
    navbar_collapse_button.append(button_span1)
    navbar_collapse_button.append(button_span2)
    navbar_collapse_button.append(button_span3)
    navbar_collapse_button.append(button_span4)
    navbar_header_div.append(navbar_collapse_button)
    
    # Add in 'Bob Dylan Lyrics' button/link and buttons/links for the
    # downloads page and the songs index
    main_index_file_rel_path = join(up_levels, main_index_html_file_name)
    a_site = Tag(name='a',
                 attrs={'href': main_index_file_rel_path,
                        'class': 'navbar-brand'})
    a_site.string = 'Bob Dylan Lyrics'
    navbar_header_div.append(a_site)
    container_div.append(navbar_header_div)
    navbar_collapse_div = Tag(name='div',
                              attrs={'class': 'navbar-collapse collapse',
                                     'id': 'bs-example-navbar-collapse-1',
                                     'aria-expanded': 'false',
                                     'style': 'height: 1px'})
    navbar_ul = Tag(name='ul', attrs={'class': 'nav navbar-nav'})
    downloads_li = Tag(name='li')
    downloads_file_rel_path = join(up_levels, file_dumps_dir,
                                   downloads_file_name)
    a_downloads = Tag(name='a', attrs={'href': downloads_file_rel_path})
    a_downloads.string = 'Downloads'
    downloads_li.append(a_downloads)
    navbar_ul.append(downloads_li)
    song_index_li = Tag(name='li')
    song_index_file_rel_path = join(up_levels, songs_dir, song_index_dir,
                                    song_index_html_file_name)
    a_song_index = Tag(name='a', attrs={'href': song_index_file_rel_path})
    a_song_index.string = 'All Songs'
    song_index_li.append(a_song_index)
    navbar_ul.append(song_index_li)
    album_index_li = Tag(name='li')
    album_index_file_rel_path = join(up_levels, albums_dir, album_index_dir,
                                     album_index_html_file_name)
    a_album_index = Tag(name='a', attrs={'href': album_index_file_rel_path})
    a_album_index.string = 'All Albums'
    album_index_li.append(a_album_index)
    navbar_ul.append(album_index_li)

    # Add in dropdown menus for albums by decade
    for decade in ['1960s', '1970s', '1980s', '1990s', '2000s', '2010s']:
        dropdown_li = Tag(name='li', attrs={'class': 'dropdown'})
        a_dropdown = Tag(name='a',
                         attrs={'href': '#',
                                'class': 'dropdown-toggle',
                                'data-toggle': 'dropdown',
                                'role': 'button',
                                'aria-haspopup': 'true',
                                'aria-expanded': 'false'})
        a_dropdown.string = decade
        caret_span = Tag(name='span', attrs={'class': 'caret'})
        a_dropdown.append(caret_span)
        dropdown_li.append(a_dropdown)
        dropdown_menu_ul = Tag(name='ul', attrs={'class': 'dropdown-menu'})
        
        # Add albums from the given decade into the decade dropdown menu
        albums_dir_rel_path = join(up_levels, albums_dir)
        decade_albums = [album for album in albums
                         if decade[:3] in album.release_date.split()[-1][:3]]
        for album in decade_albums:
            album_file_name = '{0}.html'.format(album.file_id)
            year = album.release_date.split()[-1]
            album_li = Tag(name='li')
            album_index_file_rel_path = join(albums_dir_rel_path, album_file_name)
            album_a = Tag(name='a',
                          attrs={'href': album_index_file_rel_path,
                                 'class': 'album'})
            album_a.string = '{0} ({1})'.format(album.name, year)
            album_li.append(album_a)
            dropdown_menu_ul.append(album_li)

        dropdown_li.append(dropdown_menu_ul)
        navbar_ul.append(dropdown_li)

    navbar_collapse_div.append(navbar_ul)

    # Add in search box
    search_div = Tag(name='div',
                     attrs={'class': 'col-md-3',
                            'style': 'border:0px solid;width:30%;height:auto;'})
    gcse_tag = Tag(name='gcse:search')
    search_form = Tag(name='form',
                      attrs={'class': 'navbar-form navbar-right',
                             'role': 'search'})
    gcse_tag.append(search_form)
    search_div.append(gcse_tag)
    navbar_collapse_div.append(search_div)

    container_div.append(navbar_collapse_div)
    top_level_nav.append(container_div)

    return top_level_nav


def remove_annotations(text: str) -> str:
    """
    Remove inline annotation marks and footnotes from a string
    containing raw lyrics text file(s).

    :param text: lyrics text
    :type text: str

    :returns: lyrics text
    :rtype: str

    :raises ValueError: if `text` is empty
    """

    if not text:
        raise ValueError('"text" is empty!')

    # Remove footnotes and inline annotation marks
    text = '\n'.join([line for line in text.split('\n')
                      if not line.startswith('**')])
    text = remove_inline_annotation_marks(text)

    return text


def standardize_quotes(text: str) -> str:
    """
    Replace all single/double stylized quotes with their unstylized
    counterparts.

    :param text: input text
    :type text: str

    :returns: output text
    :rtype: str
    """

    return replace_single_quotes(r"'", replace_double_quotes(r'"', text))


def clean_up_html(html: str) -> str:
    """
    Clean up HTML generated via BeautifulSoup by converting
    "&lt;"/"&gt;" character sequences to "<"/">".

    :param html: input HTML
    :type html: str

    :returns: output HTML
    :rtype: str
    """

    for sub, regex in CLEANUP_REGEXES_DICT.items():
        html = regex.sub(sub, html)

    return html


def find_annotation_indices(line: str, annotations: List[str]) -> List[int]:
    """
    Get list of annotation indices in a sentence (treating the
    annotations themselves as zero-length entities).

    :param line: original line (including annotations)
    :type line: str
    :param annotations: list of annotation values, i.e., the numbered
                        part of each annotation
    :type annotations: list

    :returns: list of indices for zero-length annotations in line
    :rtype: list
    """

    indices = []

    # Figure out the indices of the zero-length annotations
    i = 0
    annotation_index = 0
    line = line.strip().split('**')
    for part in line:
        try:
            if part == annotations[annotation_index]:
                indices.append(i)
                annotation_index += 1
                continue
        except IndexError:
            pass
        if part not in annotations:
            i += len(part)

    if len(annotations) != annotation_index:
        raise ValueError('One or more annotations were not found. annotations '
                         '= {0}, line = "{1}".'.format(annotations, line))

    return indices


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
        index_file.write(add_declaration(clean_up_html(str(html))))


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
                sys.stderr.write('The number of expected songs ({0}) for the '
                                 'given side/disc ({1}) does not equal the '
                                 'number of songs actually included on the '
                                 'side/disc ({2}).'
                                 .format(expected_number_of_songs, section,
                                         added_songs))

            ol.append(inner_ol)
            ol.append(Tag(name='p'))
    else:
        [ol.append(generate_song_list_element(song)) for song in songs]

    columns_div.append(ol)
    
    return columns_div


def htmlify_everything(albums: List[Album], song_files_dict: SongFilesDictType,
                       make_downloads: bool = False) -> None:
    """
    Create HTML files for the main index page, each album's index page,
    and the pages for all songs.

    :param albums: list of Album objects
    :type albums: List[Album]
    :param song_files_dict: dictionary mapping song names to lists of
                            versions
    :type song_files_dict: dict
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool

    :returns: None
    :rtype: None
    """

    # Generate index page for albums
    sys.stderr.write('HTMLifying the albums index page...\n')

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
        albums_index.write(add_declaration(index_html.prettify(formatter="html")))

    # Generate pages for albums
    sys.stderr.write('HTMLifying the individual album pages...\n')
    [htmlify_album(album, albums, make_downloads=make_downloads)
     for album in albums]

    # Generate the main song index page
    sys.stderr.write('HTMLifying the main song index page...\n')
    htmlify_main_song_index_page(song_files_dict, albums)

    # Generate the main album index page
    sys.stderr.write('HTMLifying the main album index page...\n')
    htmlify_main_album_index_page(albums)


def htmlify_album(album: Album, albums: List[Album],
                  make_downloads: bool = False) -> None:
    """
    Generate HTML pages for a particular album and its songs.

    :param album: Album object
    :type name: Album
    :param albums: list of all Album objects
    :type albums: List[Album]
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying index page for {}...\n'.format(album.name))

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
        album_file.write(add_declaration(clean_up_html(str(html))))

    # Generate HTML files for each song (unless a song is indicated as
    # having appeared on previous album(s) since this new instance of
    # the song will simply reuse the original lyrics file) and,
    # optionally, add song texts to the
    # `song_texts`/`unique_song_texts` lists so that lyrics file
    # downloads can be generated at the end of processing
    for song in album.songs:

        # HTMLify the song
        if (not song.instrumental and
            not song.source and
            not song.written_and_performed_by):
            htmlify_song(song, albums)

        # Add song text to the `song_texts`/`unique_song_texts` lists
        # for the lyrics file downloads
        if (make_downloads and
            not song.instrumental and
            not song.written_and_performed_by):

            input_path = join(root_dir_path, text_dir_path,
                              '{0}.txt'.format(song.file_id))
            with open(input_path) as song_file:
                song_text = song_file.read()
                standardized_song_text = standardize_quotes(song_text).strip()
                no_annotations_song_text = \
                    remove_annotations(standardized_song_text)
                song_texts.append(no_annotations_song_text)
                unique_song_texts.add(no_annotations_song_text)


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
    """

    file_id = song.file_id
    name = song.name
    sys.stderr.write('HTMLifying {}...\n'.format(name))

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
    with open(input_path) as raw_song_lyrics_file:
        song_lines = \
            standardize_quotes(raw_song_lyrics_file.read()).strip().splitlines()
    paragraphs = []
    current_paragraph = []
    annotations = []
    for line_ind, line in enumerate(song_lines):
        if line.strip():

            # If the line begins with two asterisks in a row, that
            # means that it is an annotation line
            if line.startswith('**'):
                annotations.append(line.strip().split(' ', 1)[1])
                continue
            current_paragraph.append(line.strip())
            if len(song_lines) == line_ind + 1:
                paragraphs.append(current_paragraph)
                current_paragraph = []
        else:
            paragraphs.append(current_paragraph)
            current_paragraph = []

    # Add paragraph elements with sub-elements of type `div` to the
    # `body` element
    row_div = Tag(name='div', attrs={'class': 'row'})
    columns_div = Tag(name='div', attrs={'class': 'col-md-12'})
    for paragraph in paragraphs:
        paragraph_elem = Tag(name='p')
        for line_elem in paragraph:

            # Create new `div` element to store the line
            div = Tag(name='div')

            # Check if line has annotations
            annotation_nums = ANNOTATION_MARK_RE.findall(line_elem)
            if annotation_nums:

                # Get indices for the annotations in the given line
                annotation_inds = find_annotation_indices(line_elem,
                                                          annotation_nums)

                # Remove annotation marks from the line
                line_elem = remove_inline_annotation_marks(line_elem)

                # Copy the contents of the line (after removing the
                # annotations) into the `div` element
                div.string = line_elem

                # Iterate over the annotations, generating anchor
                # elements that link the annotation to the note at the
                # bottom of the page
                for i, annotation_num in enumerate(annotation_nums):
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
                        # annotations after will necessarily change as
                        # they will be pushed back by the length of the
                        # string that is being added
                        for j in range(len(annotation_inds)):
                            if j > i:
                                annotation_inds[j] += len(a.string)
            else:

                # Copy the contents of the line into the `div` element
                div.string = line_elem

            # Insert the `div` element into the paragraph element
            paragraph_elem.append(div)

        columns_div.append(paragraph_elem)

    # Add in annotation section
    if annotations:
        annotation_section = Tag(name='p')

        # Iterate over the annotations, assuming the the index of the
        # list matches the natural ordering of the annotations
        for annotation_num, annotation in enumerate(annotations):
            div = Tag(name='div')
            div.string = '\t{}'.format(annotation)
            div.string.wrap(Tag(name='small'))

            # Generate a named anchor element so that the original
            # location of the annotation in the song can be linked to
            # this location
            a = Tag(name='a', attrs={'name': str(annotation_num + 1)})
            a.string = str(annotation_num + 1)
            a.string.wrap(Tag(name='sup'))
            div.small.insert_before(a)
            annotation_section.append(div)

        # Insert annotation section at the next index
        columns_div.append(annotation_section)

    # Add content to body and put body in HTML element
    row_div.append(columns_div)
    container_div.append(row_div)
    body.append(container_div)
    html.append(body)

    # Write out "prettified" HTML to the output file
    html_output_path = join(songs_dir, 'html', '{0}.html'.format(file_id))
    with open(join(root_dir_path, html_output_path), 'w') as song_file:
        song_file.write(add_declaration(clean_up_html(str(html))))


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

    sys.stderr.write('HTMLifying the main songs index page...\n')

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
        songs_index_file.write(add_declaration(clean_up_html(str(html))))


def sort_titles(titles: Iterable[str], filter_char: str = None) -> List[str]:
    """
    Sort a list of strings (ignoring leading "The" or "A" or
    parentheses).

    :param titles: an iterable collection of strings (song titles,
                   album titles)
    :type titles: Iterable[str]
    :param filter_char: character on which to filter the strings, i.e.
                        strings not beginning with this character --
                        after being cleaned -- will be filtered out
    :type filter_char: str

    :returns: string generator
    :rtype: filter

    :raises: ValueError if any of the strings are empty or there are no
             strings at all
    """

    if not titles:
        raise ValueError('Received empty list!')

    filter_func = (lambda x: filter_char.lower() == get_title_index_letter(x)
                   if filter_char
                   else None)
    return filter(filter_func, sorted(titles, key=clean_title))


def and_join_album_links(albums: List[Dict[str, str]]) -> str:
    """
    Concatenate one or more albums together such that if it's two, then
    then they are concatenated by the word "and" padded by spaces, if
    there's more than two, they're separated by a comma followed by a
    space except for the last two which are separated with the word
    "and" as above, and, if there's only one, there's no need to do any
    special concatenation. Also, each album name should be wrapped in
    an "a" tag with "href" pointing to the album's index page.

    :param albums: list of dictionaries containing the album names/file
                   IDs (in 'file_id'/'name' keys)
    :type albums: list

    :returns: string representing the concatenation of album titles,
              with each one being surrounded by a link tag pointing to
              the album's index page
    :rtype: str

    :raises: ValueError if there are no albums or expected keys in the
             album dictionaries are not present
    """

    if not len(albums): raise ValueError('No albums!')

    link_template = '<a href="../../albums/{0}.html">{1}</a>'
    link = (lambda x: link_template.format(x['file_id'], x['name']))

    if len(albums) == 1:
        return link(cytoolz.first(albums))
    else:
        last_two = ' and '.join([link(album) for album in albums[-2:]])
        if len(albums) > 2:
            return ', '.join([link(album) for album in albums[:-2]] + [last_two])
        return last_two


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
                div.append('{0} '.format(song))
                comment = Tag(name='comment')
                comment.string = ('({0}, appeared on {1})'
                                  .format(instrumental_or_not_dylan,
                                          album_links))
                div.append(comment)
                row_div.append(div)
                columns_div.append(row_div)
            else:
                song_html_file_path = \
                    '../html/{0}.html'.format(song_info['file_id'])
                a_song = Tag(name='a', attrs={'href': song_html_file_path})
                a_song.string = '{0} '.format(song)
                div.append(a_song)
                comment = Tag(name='comment')
                comment.string = '(appeared on {0})'.format(album_links)
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
        letter_index_file.write(add_declaration(clean_up_html(str(html))))

    return True


def htmlify_main_album_index_page(albums: List[Album]):
    """
    Generate the main album index HTML page.

    :param albums: list of Album objects
    :type albums: List[Album]

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying the main albums index page...\n')

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
        albums_index_file.write(add_declaration(clean_up_html(str(html))))


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
        letter_index_file.write(add_declaration(clean_up_html(str(html))))

    return True


def write_big_lyrics_files() -> None:
    """
    Process the raw lyrics files stored in `song_texts` and
    `unique_song_texts` (i.e., after `htmlify_song` has been run on
    each song) and then write big files containing all of the lyrics
    files in the order in which they were added.

    :returns: None
    :rtype: None
    """

    newline_join = '\n'.join

    # Write big file with all songs (even duplicates)
    song_text_lines = newline_join(song_texts).split('\n')
    song_text = newline_join([line.strip() for line in song_text_lines
                              if line.strip()])
    song_text_path = join(file_dumps_dir_path, all_songs_file_name)
    with open(song_text_path, 'w') as song_text_file:
        song_text_file.write(song_text)

    # Write big file with all songs (no duplicates)
    unique_song_text_lines = newline_join(unique_song_texts).split('\n')
    unique_song_text = newline_join([line.strip() for line
                                     in unique_song_text_lines if line.strip()])
    unique_song_text_path = join(file_dumps_dir_path,
                                 all_songs_unique_file_name)
    with open(unique_song_text_path, 'w') as unique_song_text_file:
        unique_song_text_file.write(unique_song_text)


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
    for file_name in [all_songs_file_name, all_songs_unique_file_name]:
        if 'unique' in file_name:
            text = 'All unique songs'
        else:
            text = ('All songs in the order in which they appeared on released'
                    ' albums')
        download_a = ('<a href={0} download>{1}</a> (up to and including {2}) '
                      '({3} KiB)'
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
        downloads_file.write(add_declaration(clean_up_html(str(html))))


def main():
    parser = ArgumentParser(conflict_handler='resolve',
                            formatter_class=ArgumentDefaultsHelpFormatter,
                            description='Generates HTML files based largely '
                                        'on the contents of the '
                                        'albums_and_songs_index.jsonlines '
                                        'file and on the raw text files that '
                                        'contain the lyrics.')
    parser.add_argument('--generate_lyrics_download_files', '-make_downloads',
                        help='Generate download files containing all of the '
                             'lyrics (both all of the songs concatenated '
                             'together and all of the unique songs in the '
                             'order of their appearance).',
                        action='store_true',
                        default=False)
    args = parser.parse_args()

    # Arguments
    make_downloads = args.generate_lyrics_download_files

    # Read in contents of the albums_and_songs_index.jsonlines file,
    # constructing a dictionary of albums and the associated songs,
    # etc.
    sys.stderr.write('Reading the albums_and_songs_index.jsonlines file and '
                     'building up index of albums and songs...\n')
    albums, song_files_dict = \
        read_songs_index(songs_and_albums_index_json_file_path)

    # Generate HTML files for the main index page, albums, songs, etc.
    sys.stderr.write('Generating HTML files for the main page, albums, songs, '
                     'etc....\n')
    generate_index_page(albums)
    htmlify_everything(albums, song_files_dict, make_downloads=make_downloads)

    # Write raw lyrics files (for downloading), if requested
    if make_downloads:
        sys.stderr.write('Generating the full lyrics download files...\n')
        write_big_lyrics_files()
        htmlify_downloads_page(albums)

    sys.stderr.write('Program complete.\n')


if __name__ == '__main__':
    main()
