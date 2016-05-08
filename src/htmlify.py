import re
import sys
import string
from json import loads
from os.path import join, exists, dirname, basename
from collections import OrderedDict

from typing import Any, Dict, List, Iterable
from bs4.element import Tag
from bs4 import BeautifulSoup
from cytoolz import first as firzt
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

# Paths
project_dir = dirname(dirname(__file__))
albums_dir = join(project_dir, 'albums')
songs_dir = join(project_dir, 'songs')
index_file_path = join(project_dir, 'albums_and_songs_index.jsonlines')
txt_dir = join(songs_dir, 'txt')
html_dir = join(songs_dir, 'html')
main_index_html_file_name = 'index.html'
song_index_dir = join(songs_dir, 'song_index')
song_index_html_file_name = 'song_index.html'
albums_index_html_file_name = 'albums.html'
songs_index_html_file_path = join(song_index_dir, song_index_html_file_name)
file_dumps_dir = join(project_dir, 'full_lyrics_file_dumps')

# BeautifulSoup-related
soup = BeautifulSoup('', 'html.parser')

# Bootstrap/HTML/Javascript/CSS-related
bootstrap_style_sheet = 'http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css'
custom_style_sheet_name = join('resources', 'stof-style.css')
jquery_script_url = 'https://ajax.googleapis.com/ajax/libs/jquery/1.11.3/jquery.min.js'
bootstrap_script_url = 'http://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js'

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
clean = lambda x: x.strip('()').lower()

# For collecting all of the song texts together to write big files
song_texts = []
unique_song_texts = set()
song_files_dict = {}
file_id_types_to_skip = ['instrumental', 'not_written_or_peformed_by_dylan']


def make_head_element(levels_up=0) -> Tag:
    """
    Make a head element including stylesheets, Javascript, etc.

    :param levels_up: how many "levels up" (relative to the the current
                      file) it takes to get to the root directory (i.e.,
                      that containing the 'resources' directory)
    :type levels_up: int

    :returns: HTML head element
    :rtype: bs4.Tag
    """

    head = soup.new_tag('head')
    head.append(soup.new_tag('meta', charset="utf-8"))
    meta_tag = soup.new_tag('meta')
    meta_tag.attrs['name'] = 'viewport'
    meta_tag.attrs['content'] = 'width=device-width, initial-scale=1'
    head.append(meta_tag)
    head.append(soup.new_tag('link', rel="stylesheet", href=bootstrap_style_sheet))
    custom_style_sheet_relative_path = join('..', '..', custom_style_sheet_name)
    head.append(soup.new_tag('link', rel="stylesheet", href=custom_style_sheet_relative_path))
    head.append(soup.new_tag('script', src=jquery_script_url))
    head.append(soup.new_tag('script', src=bootstrap_script_url))

    return head


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
    text = '\n'.join([line for line in text.split('\n') if not line.startswith('**')])
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
    :param annotation_nums: list of annotation values, i.e., the
                            numbered part of each annotation
    :type annotation_nums: list

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
        if not part in annotations:
            i += len(part)

    if len(annotations) != annotation_index:
        raise ValueError('One or more annotations were not found. annotations '
                         '= {0}, line = "{1}".'.format(annotations, line))

    return indices


def read_songs_index() -> Dict[str, Any]:
    """
    Read albums_and_songs_index.jsonlines file and make dictionary
    representation.

    :returns: albums dictionary
    :rtype: dict

    :raises: ValueError
    """

    albums = OrderedDict()
    for album_or_song_dict in (loads(line.strip('\n')) for line in open(index_file_path)
                               if not line.startswith('#') and line.strip('\n')):

        if album_or_song_dict['type'] == 'album':

            # Make a dictionary that has keys 'attrs' mapped to the
            # album attributes, i.e., metadata, and 'songs' mapped to
            # an ordered dictionary of songs where the keys are song
            # names and the values are dictionaries containing the file
            # IDs and a key 'from' mapped to the name/file ID of the
            # original album that the song came from (only if the song
            # came from a previous album; otherwise, this will be set
            # to None)
            attrs = album_or_song_dict['metadata']
            songs = attrs['songs']
            del attrs['songs']
            sorted_songs = sorted(songs.items(), key=lambda x: x[1]['index'])
            ordered_songs = OrderedDict((song_id,
                                         {'file_id': song_dict['file_id'],
                                          'from': song_dict.get('from', ''),
                                          'sung_by': song_dict.get('sung_by', ''),
                                          'instrumental': song_dict.get('instrumental', ''),
                                          'written_and_performed_by':
                                              song_dict.get('written_and_performed_by', {})})
                                        for song_id, song_dict in sorted_songs)
            albums[attrs['name']] = {'attrs': attrs, 'songs': ordered_songs}

        elif album_or_song_dict['type'] == 'song':

            # Define the actions to take when an entry only contains a
            # single song (when this comes up eventually)
            # NOTE: Remember to deal with adding the lyrics of the song
            # in question to the list of song lyrics.
            pass

        else:
            raise ValueError('Encountered a JSON object whose "type" '
                             'attribute is neither "album" nor "song".')

    if not albums:
        raise ValueError('No albums found in albums_and_songs_index.jsonlines'
                         ' file!')

    return albums


def generate_song_list_element(song_name: str, song_dict: Dict[str, Any]) -> Tag:
    """
    Make a list element for a song (for use when generating an album
    webpage, for example).

    :param song_name: name of song
    :type song_name: str
    :param song_dict: dictionary containing song attributes
    :type song_dict: dict

    :returns: HTML list element
    :rtype: bs4.element.Tag
    """

    # Make a list element for the song
    li = soup.new_tag('li')
    from_song = song_dict['from']
    sung_by = song_dict['sung_by']
    performed_by = song_dict['written_and_performed_by'].get('performed_by', '')

    # If the song was sung by someone other than Bob Dylan, there will
    # be a "sung_by" key whose value will be the actual (and primary)
    # singer of the song, which should appear in a parenthetical
    # comment. On the other hand, if the song was both performed by
    # someone other than Bob Dylan (primarily, at least) and written by
    # someone other than Bob Dyaln (primarily, again), then there will
    # be a special "written_and_performed_by" key.
    if sung_by:
        sung_by = ' (sung by {0})'.format(sung_by)
    elif performed_by:
        performed_by = ' (performed by {0})'.format(performed_by)
    instrumental = ' (Instrumental)' if song_dict['instrumental'] else ''
    if not instrumental and not performed_by:
        song_file_path = join('..', 'songs', 'html', '{0}.html'.format(song_dict['file_id']))
        a_song = soup.new_tag('a', href=song_file_path)
    if from_song:
        if not instrumental and not performed_by:
            a_song.string = song_name
            orig_album_file_path = join('..', 'albums', '{0}'.format(from_song['file_id']))
            a_orig_album = soup.new_tag('a', href=orig_album_file_path)
            a_orig_album.string = from_song['name']
            a_orig_album.string.wrap(soup.new_tag('i'))

            # Construct the string content of the list element including
            # information about the original song/album, a comment that
            # the song is an instrumental song if that applies, and a
            # comment that the song was sung by someone else if that
            # applies
            li.string = '{0} (appeared on {1}{2})'.format(a_song, a_orig_album, sung_by)
        else:
            li.string = '{0}{1}{2}'.format(song_name, instrumental, performed_by)
    else:

        # Construct the string content of the list element including a
        # comment that the song is an instrumental song if that applies,
        # and a comment that the song was sung by someone else or is
        # basically just not a Bob Dylan song, if either of those
        # applies
        li.string = '{0}{1}{2}{3}'.format(song_name, instrumental, sung_by, performed_by)
        if not instrumental and not performed_by:
            li.string.wrap(a_song)
        
    # Italicize/gray out song entries if they do not contain lyrics
    if instrumental or performed_by:
        li.string.wrap(soup.new_tag('i'))
        li.string.wrap(soup.new_tag('font', color='#726E6D'))

    return li


def generate_song_list(songs: OrderedDict, sides_dict: Dict[str, str] = None) -> Tag:
    """
    Generate an HTML element representing an ordered list of songs.

    If `sides_dict`

    :param songs: ordered dictionary of song names mapped to song
                  IDs/info regarding the source of the song (in cases
                  where the album is a compilation album)
    :type songs: OrderedDict
    :param sides_dict: dictionary mapping side indices to song index
                       ranges, i.e., "1" -> "1-5"
    :type sides_dict: dict

    :returns: ordered list element
    :rtype: bs4.element.Tag

    :raises: ValueError if information about sides contains conflicts
             with assumptions
    """

    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    ol = soup.new_tag('ol')
    if sides_dict:
        for side in sorted(sides_dict):

            # Make sure the side is interpretable as an integer
            try:
                if int(side) < 1:
                    raise ValueError
            except ValueError:
                raise ValueError('Each side ID should be interpretable as an '
                                 'integer that is greater than zero. Offending'
                                 ' side ID: "{0}".'.format(side))

            side_div = soup.new_tag('div')
            side_div.string = "Side {0}".format(side)
            ol.append(side_div)
            ol.append(soup.new_tag('p'))
            inner_ol = soup.new_tag('ol')

            # Each side will have an associated range of song numbers,
            # e.g. "1-5" (unless a side contains only a single song, in
            # which case it will simply be the song number by itself)
            if '-' in sides_dict[side]:
                first, last = sides_dict[side].split('-')
                try:
                    if int(first) < 1:
                        raise ValueError
                    if int(last) < 1:
                        raise ValueError
                    if int(last) <= int(first):
                        raise ValueError
                except ValueError:
                    raise ValueError("Each side's associated range should "
                                     "consist of integer values greater than "
                                     "zero and the second value should be "
                                     "greater than the first. Offending range:"
                                     " \"{0}\".".format(sides_dict[side]))
            else:
                first = last = sides_dict[side]
                try:
                    if int(first) < 1:
                        raise ValueError
                except ValueError:
                    raise ValueError("Each side's associated range can consist"
                                     " of a single value, but that value "
                                     "should be an integer greater than zero. "
                                     "Offending range: \"{0}\"."
                                     .format(sides_dict[side]))

            # Get the expected number of songs for the given side
            expected_number_of_songs = int(last) - int(first) + 1
            added_songs = 0
            for index, song in enumerate(songs):
                try:
                    if index + 1 in range(int(first), int(last) + 1):
                        inner_ol.append(generate_song_list_element(song, songs[song]))
                        added_songs += 1
                    if int(last) == index + 1:
                        break
                except TypeError as e:
                    raise ValueError('The "sides" attribute contains invalid '
                                     'song indices: {0}.'.format(sides_dict[side]))

            # Make sure the correct number of songs were included
            if added_songs != expected_number_of_songs:
                sys.stderr.write('The number of expected songs ({0}) for the '
                                 'given side ({1}) does not equal the number '
                                 'of songs actually included on the side '
                                 '({2}).'
                                 .format(expected_number_of_songs, side, added_songs))

            ol.append(inner_ol)
            ol.append(soup.new_tag('p'))
    else:
        for song in songs:
            ol.append(generate_song_list_element(song, songs[song]))

    columns_div.append(ol)
    row_div.append(columns_div)
    
    return row_div


def htmlify_everything(albums: Dict[str, Any], make_downloads: bool = False) -> None:
    """
    Create HTML files for the albums index page, each album, and each
    song.

    :param albums: dictionary of album names mapped to a dictionary
                   containing an album attribute dictionary, including
                   attributes such as the HTML file name, the release
                   date, etc., and an ordered dictionary of songs,
                   including song file IDs and information about where
                   the songs come from (if they were from a previous
                   album, as in the case of compilation albums, for
                   instance)
    :type albums: dict
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool

    :returns: None
    :rtype: None
    """

    # Generate index page for albums
    sys.stderr.write('HTMLifying the albums index page...\n')

    # Make HTML element for albums index page
    index_html = soup.new_tag('html')

    # Generate body for albums page
    index_body = soup.new_tag('body')

    # Add in elements for the heading
    index_heading = soup.new_tag('h1')
    index_heading.string = 'Albums'
    index_heading.string.wrap(soup.new_tag('a', href=albums_index_html_file_name))
    index_body.append(index_heading)

    # Add in ordered list element for all albums
    index_ol = soup.new_tag('ol')
    for album in albums:
        album_html_file_name = '{}.html'.format(albums[album]['attrs']['file_id'])
        album_html_file_path = join('albums', album_html_file_name)
        year = albums[album]['attrs']['release_date'].split()[-1]
        li = soup.new_tag('li')
        li.string = '{0} ({1})'.format(album, year)
        li.string.wrap(soup.new_tag('a', href=album_html_file_path))
        index_ol.append(li)
    index_body.append(index_ol)

    # Add in "Home" link
    div = soup.new_tag('div')
    div.string = 'Home'
    div.string.wrap(soup.new_tag('a', href=main_index_html_file_name))
    index_body.append(div)

    # Put body in HTML element
    index_html.append(index_body)

    # Write new HTML file for albums index page
    with open(join(project_dir, albums_index_html_file_name), 'w') as albums_index:
        albums_index.write(index_html.prettify(formatter="html"))

    # Generate pages for albums
    sys.stderr.write('HTMLifying the individual album pages...\n')
    for album, attrs_songs in albums.items():
        htmlify_album(album, attrs_songs['attrs'], attrs_songs['songs'],
                      make_downloads=make_downloads)


def htmlify_album(name: str, attrs: Dict[str, Any], songs: OrderedDict,
                  make_downloads: bool = False) -> None:
    """
    Generate HTML pages for a particular album and its songs.

    :param name: name of the album
    :type name: str
    :param attrs: dictionary of album attributes, including the name of
                  the HTML file corresponding to the given album
    :type attrs: dict
    :param songs: ordered dictionary of song names mapped to song
                  IDs/info regarding the source of the song (in cases
                  where the album is a compilation album)
    :type songs: OrderedDict
    :param make_downloads: True if lyrics file downloads should be
                           generated
    :type make_downloads: bool

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying index page for {}...\n'.format(name))

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = soup.new_tag('html')
    html.append(make_head_element(1))

    # Generate body for albums page
    body = soup.new_tag('body')

    # Create div tag for the "container"
    container_div = soup.new_tag('div')
    container_div.attrs['class'] = 'container'

    # Add in elements for the heading
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    heading = soup.new_tag('h1')
    heading.string = name
    columns_div.append(heading)
    row_div.append(columns_div)
    container_div.append(row_div)

    # Add in the album attributes, including a picture of the album
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    attrs_div = soup.new_tag('div')
    image_file_path = join('..', 'resources', 'images', attrs['image_file_name'])
    image = soup.new_tag('img', src=image_file_path)
    attrs_div.append(image)
    release_div = soup.new_tag('div')
    release_div.string = 'Released: {0}'.format(attrs['release_date'])
    attrs_div.append(release_div)
    length_div = soup.new_tag('div')
    length_div.string = 'Length: {0}'.format(attrs['length'])
    attrs_div.append(length_div)
    producers_string = attrs['producers']
    producers_string_template = ('Producer{0}: {1}'
                                 .format('' if len(producers_string.split(', ')) == 1
                                         else '(s)', '{0}'))
    producers_div = soup.new_tag('div')
    producers_div.string = producers_string_template.format(producers_string)
    attrs_div.append(producers_div)
    label_div = soup.new_tag('div')
    label_div.string = 'Label: {0}'.format(attrs['label'])
    attrs_div.append(label_div)
    columns_div.append(attrs_div)
    row_div.append(columns_div)
    container_div.append(row_div)

    # Add in an ordered list element for all songs (or several ordered
    # lists for each side, disc, etc.)
    # NOTE: Deal with the possibility of a 'discs' attribute in addition
    # to the 'sides' attribute
    container_div.append(generate_song_list(songs, attrs.get('sides', None)))

    # Add in navigation buttons
    nav_tag = soup.new_tag('ul')
    nav_tag.attrs['class'] = 'nav nav-pills'
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href='../index.html')
    a_tag.string = 'Home'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    container_div.append(nav_tag)
    body.append(container_div)

    # Put body in HTML element
    html.append(body)

    # Write new HTML file for albums index page
    album_file_path = join(albums_dir, '{}.html'.format(attrs['file_id']))
    with open(album_file_path, 'w') as album_file:
        album_file.write(clean_up_html(str(html)))

    # Generate HTML files for each song (unless a song is indicated as
    # having appeared on previous album(s) since this new instance of
    # the song will simply reuse the original lyrics file) and,
    # optionally, add song texts to the `song_texts`/`unique_song_texts`
    # lists so that lyrics file downloads can be generated at the end of
    # processing
    for song in songs:
        song_attrs = songs[song]

        # HTMLify the song
        if (not song_attrs['instrumental'] and
            not song_attrs['from'] and
            not song_attrs['written_and_performed_by']):
            htmlify_song(song, song_attrs['file_id'], '{}.html'.format(attrs['file_id']))

        # Add song text to the `song_texts`/`unique_song_texts` lists
        if (make_downloads and
            not song_attrs['instrumental'] and
            not song_attrs['written_and_performed_by']):

            input_path = join(txt_dir, '{0}.txt'.format(song_attrs['file_id']))
            song_text = remove_annotations(standardize_quotes(open(input_path).read()).strip())
            song_texts.append(song_text)
            unique_song_texts.add(song_text)

        # Add in song name/file ID and album name/file ID to
        # `song_files_dict` (for the song index), indicating if the song
        # is an instrumental or if it wouldn't be associated with an
        # actual file ID for some other reason
        if song_attrs['instrumental']:
            song_file_id = 'instrumental'
        elif song_attrs['written_and_performed_by']:
            song_file_id = 'not_written_or_peformed_by_dylan'
        else:
            song_file_id = song_attrs['file_id']
        if not song in song_files_dict:
            file_album_dict = {'name': name, 'file_id': attrs['file_id']}
            song_files_dict[song] = [{'file_id': song_file_id,
                                      'album(s)': [file_album_dict]}]
        else:

            # Iterate over the entries in `song_files_dict` for a given
            # song, each entry corresponding to a different `file_id`
            # (basically, a different version of the same song) and, if
            # an entry for the song's file ID is found, add its album to
            # the list of albums associated with that file ID/version,
            # and, if not, then add the file ID/version to the list of
            # versions associated with the song (i.e., with its own list
            # of albums)
            # TODO: This assumes that all songs are attached to the same
            #       exact name whenever they show up on an album, but
            #       this is not strictly true, e.g. "Crash on the Levee
            #       (Down in the Flood)."
            found_file_id_in_song_dicts = False
            if not song_file_id in file_id_types_to_skip:
                for file_ids_dict in song_files_dict[song]:
                    if file_ids_dict['file_id'] == song_file_id:
                        file_album_dict = {'name': name, 'file_id': attrs['file_id']}
                        file_ids_dict['album(s)'].append(file_album_dict)
                        found_file_id_in_song_dicts = True
                        break
            if not found_file_id_in_song_dicts:
                file_album_dict = {'name': name, 'file_id': attrs['file_id']}
                song_files_dict[song].append({'file_id': song_file_id,
                                              'album(s)': [file_album_dict]})


def htmlify_song(name: str, song_id: str, album_id: str) -> None:
    """
    Read in a raw text file containing lyrics and output an HTML file
    (unless the song is an instrumental and contains no lyrics).

    :param name: song name
    :type name: str
    :param song_id: song file ID
    :type song_id: str
    :param album_id: album file ID
    :type album_id: str

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying {}...\n'.format(name))

    input_path = join(txt_dir, '{0}.txt'.format(song_id))
    html_file_name = '{0}.html'.format(song_id)
    html_output_path = join(html_dir, html_file_name)

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = soup.new_tag('html')
    html.append(make_head_element(2))

    # Body element
    body = soup.new_tag('body')

    # Make a tag for the name of the song
    container_div = soup.new_tag('div')
    container_div.attrs['class'] = 'container'
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    h_tag = soup.new_tag('h1')
    h_tag.string = name
    columns_div.append(h_tag)
    row_div.append(columns_div)
    container_div.append(row_div)

    # Process lines from raw lyrics file into different paragraph
    # elements
    song_lines = standardize_quotes(open(input_path).read()).strip().split('\n')
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
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    for paragraph in paragraphs:
        paragraph_elem = soup.new_tag('p')
        for line_elem in paragraph:

            # Create new `div` element to store the line
            div = soup.new_tag('div')

            # Check if line has annotations
            annotation_nums = ANNOTATION_MARK_RE.findall(line_elem)
            if annotation_nums:

                # Get indices for the annotations in the given line
                annotation_inds = find_annotation_indices(line_elem, annotation_nums)

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
                    a = soup.new_tag('a', href=href)
                    a.string = annotation_num
                    a.string.wrap(soup.new_tag('sup'))

                    # Insert the anchor element into the `div` element
                    # at the appropriate location
                    ind = annotation_inds[i]
                    if ind == len(div.string):
                        div.string.replace_with('{0}{1}'.format(div.string, str(a)))
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
                                annotation_inds[j] = annotation_inds[j] + len(a.string)
            else:

                # Copy the contents of the line into the `div` element
                div.string = line_elem

            # Insert the `div` element into the paragraph element
            paragraph_elem.append(div)

        columns_div.append(paragraph_elem)

    # Add in annotation section
    if annotations:
        annotation_section = soup.new_tag('p')

        # Iterate over the annotations, assuming the the index of the
        # list matches the natural ordering of the annotations
        for annotation_num, annotation in enumerate(annotations):
            div = soup.new_tag('div')
            div.string = '\t{}'.format(annotation)
            div.string.wrap(soup.new_tag('small'))

            # Generate a named anchor element so that the original
            # location of the annotation in the song can be linked to
            # this location
            a = soup.new_tag('a')
            a.attrs['name'] = annotation_num + 1
            a.string = str(annotation_num + 1)
            a.string.wrap(soup.new_tag('sup'))
            div.small.insert_before(a)
            annotation_section.append(div)

        # Insert annotation section at the next index
        columns_div.append(annotation_section)

    # Add in navigation buttons
    nav_tag = soup.new_tag('ul')
    nav_tag.attrs['class'] = 'nav nav-pills'
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href='../../index.html')
    a_tag.string = 'Home'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href=join('..', '..', 'albums', album_id))
    a_tag.string = 'Back'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    columns_div.append(nav_tag)
    row_div.append(columns_div)
    container_div.append(row_div)
    body.append(container_div)

    # Put body in HTML element
    html.append(body)

    # Write out "prettified" HTML to the output file
    with open(html_output_path, 'w') as html_output:
        html_output.write(clean_up_html(str(html)))


def htmlify_main_song_index_page() -> None:
    """
    Generate the main song index HTML page.

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying the main songs index page...')

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = soup.new_tag('html')
    html.append(make_head_element(2))

    # Body element
    body = soup.new_tag('body')

    # Make a tag for the name of the song
    container_div = soup.new_tag('div')
    container_div.attrs['class'] = 'container'
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    h_tag = soup.new_tag('h1')
    h_tag.string = 'Songs Index'
    columns_div.append(h_tag)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(soup.new_tag('p'))

    for letter in string.ascii_uppercase:
        row_div = soup.new_tag('div')
        row_div.attrs['class'] = 'row'
        columns_div = soup.new_tag('div')
        columns_div.attrs['class'] = 'col-xs-12'
        div_tag = soup.new_tag('div')
        a_tag = soup.new_tag('a', href=join('{0}.html'.format(letter.lower())))
        a_tag.string = letter
        bold_tag = soup.new_tag('strong')
        bold_tag.attrs['style'] = 'font-size: 125%;'
        a_tag.string.wrap(bold_tag)
        div_tag.append(a_tag)
        columns_div.append(div_tag)
        row_div.append(columns_div)
        container_div.append(row_div)

        # Generate the sub-index page for the letter
        htmlify_song_index_page(letter)

    # Add in navigation buttons
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    nav_tag = soup.new_tag('ul')
    nav_tag.attrs['class'] = 'nav nav-pills'
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href='../../index.html')
    a_tag.string = 'Home'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    columns_div.append(nav_tag)
    row_div.append(columns_div)
    container_div.append(row_div)

    body.append(container_div)
    html.append(body)

    with open(songs_index_html_file_path, 'w') as songs_index_page:
        songs_index_page.write(clean_up_html(str(html)))


def sort_titles(titles: Iterable[str], filter_char: str = None) -> List[str]:
    """
    Sort a list of strings (ignoring leading "The" or "A" or
    parentheses).

    :param titles: an iterable collection of strings (song titles, album
                   titles)
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

    if not titles or not all(x for x in titles):
        raise ValueError('Received empty string!')

    key_func = lambda x: A_THE_RE.sub(r'', clean(x))
    filter_func = None
    if filter_char:
        filter_func = lambda x: filter_char.lower() == firzt(A_THE_RE.sub(r'', clean(x)))
    return filter(filter_func, sorted(titles, key=key_func))


def and_join_album_links(albums: List[Dict[str, str]]) -> str:
    """
    Concatenate one or more albums together such that if it's two, then
    then they are concatenated by the word "and" padded by spaces, if
    there's more than two, they're separated by a comma followed by a
    space except for the last two which are separated with the word
    "and" as above, and, if there's only one, there's no need to do any
    special concatenation. Also, each album name should be wrapped in an
    "a" tag with "href" pointing to the album's index page.

    :param albums: list of dictionaries containing the album
                   names/file IDs (in 'file_id'/'name' keys)
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
        return link(firzt(albums))
    else:
        last_two = ' and '.join([link(album) for album in albums[-2:]])
        if len(albums) > 2:
            return ', '.join(', '.join([link(album) for album in albums[:-2]]), last_two)
        return last_two


def htmlify_song_index_page(letter: str) -> None:
    """
    Generate a specific index page.

    :param letter: index letter
    :type letter: str

    :returns: None
    :rtype: None
    """

    # Make BeautifulSoup object and append head element containing
    # stylesheets, Javascript, etc.
    html = soup.new_tag('html')
    html.append(make_head_element(2))

    # Body element
    body = soup.new_tag('body')

    # Make a tag for the name of the song
    container_div = soup.new_tag('div')
    container_div.attrs['class'] = 'container'
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    h_tag = soup.new_tag('h1')
    h_tag.string = letter
    columns_div.append(h_tag)
    row_div.append(columns_div)
    container_div.append(row_div)
    container_div.append(soup.new_tag('p'))

    not_dylan = 'not written by or not performed by Bob Dylan'
    for song in sort_titles(song_files_dict, letter):

        # Get information about the song, such as the different versions
        # of the song, their file IDs, which albums they occurred on,
        # whether they were instrumentals, etc.
        song_info = song_files_dict[song]

        row_div = soup.new_tag('div')
        row_div.attrs['class'] = 'row'
        columns_div = soup.new_tag('div')
        columns_div.attrs['class'] = 'col-xs-12'
        div_tag = soup.new_tag('div')
        if len(song_info) == 1:
            song_info = firzt(song_info)
            album_links = and_join_album_links(song_info['album(s)'])

            if song_info['file_id'] in file_id_types_to_skip:
                instrumental_or_not_dylan = song_info['file_id']
                if instrumental_or_not_dylan != 'instrumental':
                    instrumental_or_not_dylan = not_dylan
                div_tag.string = ('{0} ({1}, appeared on {2})'
                                  .format(song, instrumental_or_not_dylan, album_links))
                row_div.append(div_tag)
                columns_div.append(row_div)
            else:
                song_html_file_path = '../html/{0}.html'.format(song_info['file_id'])
                a_tag = soup.new_tag('a', href=song_html_file_path)
                a_tag.string = '{0}'.format(song)
                div_tag.append(a_tag)
                div_tag.append = ' (appeared on {0})'.format(album_links)

        else:
            div_tag.string = song
            columns_div.append(div_tag)

            # Make an unordered list for the different versions of the
            # song
            ul_tag = soup.new_tag('ul')
            for i, version_info in enumerate(song_info):
                li_tag = soup.new_tag('li')

                # Add in instrumental entries (but with no link to the
                # song pages since they don't exist), but don't even add
                # in entries for the songs that have been deemed as
                # non-Dylan songs
                if version_info['file_id'] == 'instrumental':
                    album_links = and_join_album_links(version_info['album(s)'])
                    li_tag.string = 'Instrumental version (appeared on {0})'.format(album_links)
                elif version_info['file_id'] == 'not_written_or_peformed_by_dylan':
                    continue
                else:
                    album_links = and_join_album_links(version_info['album(s)'])
                    href = '../html/{0}.html'.format(version_info['file_id'])
                    a_tag = soup.new_tag('a', href=href)
                    a_tag.string = 'Version #{0}'.format(i + 1)
                    li_tag.append(a_tag)
                    li_tag.append(' (appeared on {0})'.format(album_links))
                ul_tag.append(li_tag)
            div_tag.append(ul_tag)
        row_div.append(div_tag)
        columns_div.append(row_div)
        container_div.append(columns_div)

    # Add in navigation buttons
    row_div = soup.new_tag('div')
    row_div.attrs['class'] = 'row'
    columns_div = soup.new_tag('div')
    columns_div.attrs['class'] = 'col-xs-12'
    nav_tag = soup.new_tag('ul')
    nav_tag.attrs['class'] = 'nav nav-pills'
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href='../../index.html')
    a_tag.string = 'Home'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    li_tag = soup.new_tag('li')
    li_tag.attrs['role'] = 'presentation'
    li_tag.attrs['class'] = 'active'
    a_tag = soup.new_tag('a', href='song_index.html')
    a_tag.string = 'Back'
    li_tag.append(a_tag)
    nav_tag.append(li_tag)
    columns_div.append(nav_tag)
    row_div.append(columns_div)
    container_div.append(row_div)

    body.append(container_div)
    html.append(body)

    letter_index_file_path = join(song_index_dir, '{0}.html'.format(letter.lower()))
    with open(letter_index_file_path, 'w') as letter_index_page:
        letter_index_page.write(clean_up_html(str(html)))


def write_big_lyrics_files() -> None:
    """
    Process the raw lyrics files stored in `song_texts` and
    `unique_song_texts` (i.e., after `htmlify_song` has been run on each
    song) and then write big files containing all of the lyrics files in
    the order in which they were added.

    :returns: None
    :rtype: None
    """

    newline_join = '\n'.join

    # Write big file with all songs (even duplicates)
    song_text_lines = newline_join(song_texts).split('\n')
    song_text = newline_join([line.strip() for line in song_text_lines if line.strip()])
    song_text_path = join(file_dumps_dir, 'all_songs.txt')
    with open(song_text_path, 'w') as song_text_file:
        song_text_file.write(song_text)

    # Write big file with all songs (no duplicates)
    unique_song_text_lines = newline_join(unique_song_texts).split('\n')
    unique_song_text = newline_join([line.strip() for line in unique_song_text_lines
                                     if line.strip()])
    unique_song_text_path = join(file_dumps_dir, 'all_songs_unique.txt')
    with open(unique_song_text_path, 'w') as unique_song_text_file:
        unique_song_text_file.write(unique_song_text)


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
    # constructing a dictionary of albums and the associated songs, etc.
    sys.stderr.write('Reading the albums_and_songs_index.jsonlines file and '
                     'building up index of albums and songs...\n')
    albums_dict = read_songs_index()

    # Generate HTML files for albums, songs, etc.
    sys.stderr.write('Generating HTML files for the albums and songs...\n')
    htmlify_everything(albums_dict, make_downloads=make_downloads)
    htmlify_main_song_index_page()

    # Write raw lyrics files (for downloading), if requested
    if make_downloads:
        sys.stderr.write('Generating the full lyrics download files...\n')
        write_big_lyrics_files()

    sys.stderr.write('Program complete.\n')


if __name__ == '__main__':
    main()
