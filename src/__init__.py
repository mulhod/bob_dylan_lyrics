"""
Collection of variables, methods, and functions that support the
functionality of the `htmlify` module. Code contained here ranges from
defining types for commonly-used data structures, organizing data
related to albums/songs into classes, providing functions for reading
in album/song metadata, and generally pre-/post-processing raw text or
HTML.
"""
import re
from json import loads
from operator import itemgetter
from collections import OrderedDict
from os.path import dirname, realpath, join
from typing import Dict, List, Union, MutableMapping, Any, Iterable, Tuple

import cytoolz
from bs4.element import Tag
from bs4 import BeautifulSoup

SongFilesDictType = Dict[str, List[Dict[str, Union[str, int, List[Dict[str, str]]]]]]
IndexDictType = List[SongFilesDictType]
SongDictType = Dict[str, Union[str, Dict[str, str]]]

file_id_types_to_skip = ['instrumental', 'not_written_or_peformed_by_dylan']

# Paths
root_dir_path = dirname(dirname(realpath(__file__)))
albums_dir = 'albums'
songs_dir = 'songs'
resources_dir = 'resources'
images_dir = 'images'
file_dumps_dir = 'full_lyrics_file_dumps'
song_index_dir = 'song_index'
album_index_dir = 'album_index'
main_index_html_file_name = 'index.html'
song_index_html_file_name = 'song_index.html'
album_index_html_file_name = 'album_index.html'
albums_index_html_file_name = 'albums.html'
custom_style_sheet_file_name = 'stof-style.css'
downloads_file_name = 'downloads.html'
all_songs_file_name = 'all_songs.txt'
all_songs_unique_file_name = 'all_songs_unique.txt'
text_dir_path = join(songs_dir, 'txt')
song_index_dir_path = join(songs_dir, song_index_dir)
songs_and_albums_index_json_file_path = join(root_dir_path,
                                             'albums_and_songs_index.json')
songs_index_html_file_path = join(root_dir_path, song_index_dir_path,
                                  song_index_html_file_name)
album_index_dir_path = join(albums_dir, album_index_dir)
albums_index_html_file_path = join(root_dir_path, album_index_dir_path,
                                   album_index_html_file_name)
file_dumps_dir_path = join(root_dir_path, file_dumps_dir)
main_index_html_file_path = join(root_dir_path, main_index_html_file_name)
home_page_content_file_path = join(root_dir_path, resources_dir,
                                   'home_page_content.md')

# Regular expression- and cleaning-related
ANNOTATION_MARK_RE = re.compile(r'\*\*([0-9]+)\*\*')
replace_inline_annotation_marks = ANNOTATION_MARK_RE.sub
remove_inline_annotation_marks = lambda x: replace_inline_annotation_marks('', x)
DOUBLE_QUOTES_RE = re.compile(r'“|”')
SINGLE_QUOTES_RE = re.compile(r'‘')
replace_double_quotes = DOUBLE_QUOTES_RE.sub
replace_single_quotes = SINGLE_QUOTES_RE.sub
CLEANUP_REGEXES_DICT = {'>': re.compile(r'&gt;'),
                        '<': re.compile(r'&lt;'),
                        '&': re.compile(r'&amp;amp;')}
A_THE_RE = re.compile(r'^(the|a) ')
substitute_determiner = A_THE_RE.sub
remove_determiner = lambda x: substitute_determiner(r'', x)
strip_parens_and_lower_case = lambda x: x.strip('()').lower()
clean_title = lambda x: remove_determiner(strip_parens_and_lower_case(x))
get_title_index_letter = lambda x: cytoolz.first(clean_title(x))

class Album():
    """
    Class for representing albums.(or collections of songs).
    """

    def __init__(self, type_: str, metadata: Dict[str, Any]):

        # Set the `type_` attribute
        self.type_ = type_

        # Extract metadata into attributes
        self.name = metadata.get('name')
        self.file_id = metadata.get('file_id')
        self.length = metadata.get('length')
        self.discs = metadata.get('discs')
        self.sides = metadata.get('sides')
        self.image_file_name = metadata.get('image_file_name')
        self.release_date = metadata.get('release_date')
        self.producers = metadata.get('producers')
        self.label = metadata.get('label')
        self.with_ = metadata.get('with', '')
        self.live = metadata.get('live', '')

        # Set the `songs` attribute
        self.songs = [Song(song_name, song_metadata)
                      for song_name, song_metadata
                      in sorted(metadata.get('songs').items(),
                                key=lambda x: itemgetter(1)(x).get('index'))]


class Song():
    """
    Class for representing song metadata.
    """

    def __init__(self, name: str, metadata: Dict[str, Any]):

        self.name = name
        self.actual_name = metadata.get('actual_name')
        self.file_id = metadata.get('file_id')
        self.source = metadata.get('source', {})
        self.sung_by = metadata.get('sung_by', '')
        self.instrumental = metadata.get('instrumental', '')
        self.written_by = metadata.get('written_by', '')
        self.written_and_performed_by = \
            metadata.get('written_and_performed_by', {})
        self.duet = metadata.get('duet', '')
        self.live = metadata.get('live', '')


def generate_lyrics_download_files(lyrics_dict: Dict[str, List[str]]) -> None:
    """
    Generate lyrics download files containing 1) all of the lyrics
    files in the order in which they were added 2) all of the unique
    lyrics.

    :param lyrics_dict: dictionary containing `song_texts` and
                        `unique_song_texts` keys associated with lists
                        of song lyrics
    :type lyrics_dict: Dict[str, List[str]]

    :returns: None
    :rtype: None
    """

    newline_join = '\n'.join

    # Write big file with all songs (even duplicates)
    song_text_lines = newline_join(lyrics_dict['song_texts']).split('\n')
    song_text = newline_join([line.strip() for line in song_text_lines
                              if line.strip()])
    song_text_path = join(file_dumps_dir_path, all_songs_file_name)
    with open(song_text_path, 'w') as song_text_file:
        song_text_file.write(song_text)

    # Write big file with all songs (no duplicates)
    unique_song_text_lines = \
        newline_join(lyrics_dict['unique_song_texts']).split('\n')
    unique_song_text = newline_join([line.strip() for line
                                     in unique_song_text_lines if line.strip()])
    unique_song_text_path = join(file_dumps_dir_path,
                                 all_songs_unique_file_name)
    with open(unique_song_text_path, 'w') as unique_song_text_file:
        unique_song_text_file.write(unique_song_text)


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
    for collection in loads('\n'.join([line for line in open(index_json_path)
                                       if not line.startswith('#')])):

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


def add_html_declaration(html_string: str) -> str:
    """
    Add in the declaration, i.e., "<!DOCTYPE html>", to the beginning
    of a string representation of an HTML file and return the new
    string.

    :param html_string: raw HTML content
    :type html_string: str

    :returns: HTML string
    :rtype: str
    """

    return str(BeautifulSoup('<!DOCTYPE html>\n{0}'.format(html_string),
                             'html.parser'))


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
