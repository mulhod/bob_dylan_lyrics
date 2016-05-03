import re
import sys
from json import loads
from os.path import join, exists, dirname, basename
from collections import OrderedDict

from typing import Any, Dict, List
from bs4.element import Tag
from bs4 import BeautifulSoup
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

# Paths
project_dir = dirname(dirname(__file__))
site_url = 'http://mulhod.github.io/bob_dylan_lyrics'
albums_dir = join(project_dir, 'albums')
songs_dir = join(project_dir, 'songs')
index_file_path = join(project_dir, 'albums_and_songs_index.jsonlines')
txt_dir = join(songs_dir, 'txt')
html_dir = join(songs_dir, 'html')
song_html_url = join(site_url, 'songs', 'html')
index_html_file_name = 'index.html'
albums_index_html_file_name = 'albums.html'
albums_index_html_file_path = join(site_url, albums_index_html_file_name)
file_dumps_dir = join(project_dir, 'full_lyrics_file_dumps')

# BeautifulSoup-related
soup = BeautifulSoup('', 'html.parser')

# Regular expression matching the expected annotation mark format
ANNOTATION_MARK = re.compile(r'\*\*([0-9]+)\*\*')
replace_inline_annotation_marks = ANNOTATION_MARK.sub
remove_inline_annotation_marks = lambda x: replace_inline_annotation_marks('', x)

# Regular expressions/functions for standardizing stylized
# double/single quotation marks
DOUBLE_QUOTES = re.compile(r'“|”')
SINGLE_QUOTES = re.compile(r'‘')
replace_double_quotes = DOUBLE_QUOTES.sub
replace_single_quotes = SINGLE_QUOTES.sub

# BeautifulSoup clean-up-related regular expressions
CLEANUP_REGEXES = {'>': re.compile(r'&gt;'),
                   '<': re.compile(r'&lt;'),
                   '&': re.compile(r'&amp;amp;')}

# For collecting all of the song texts together to write big files
song_texts = []
unique_song_texts = set()


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

    for sub, regex in CLEANUP_REGEXES.items():
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
    line = line.strip().split('**')
    for part in line:
        if part in annotations:
            indices.append(i)
            continue
        if not part in annotations:
            i += len(part)

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
                                          'from': song_dict.get('from'),
                                          'sung_by': song_dict.get('sung_by', ''),
                                          'instrumental': song_dict.get('instrumental')})
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
    from_song = song_dict.get('from')
    sung_by = song_dict.get('sung_by', '')

    # If the song was sung by someone other than Bob Dylan, there will
    # be a "sung_by" key whose value will be the actual (and primary)
    # singer of the song, which should appear in a parenthetical comment
    if sung_by:
        sung_by = ' (sung by {0})'.format(sung_by)
    instrumental = ' (Instrumental)' if song_dict.get('instrumental') else ''
    song_file_path = join(site_url, 'songs', 'html', '{0}.html'
                          .format(song_dict['file_id']))
    a_song = soup.new_tag('a', href=song_file_path)
    if from_song:
        a_song.string = song_name
        orig_album_file_path = join(site_url, 'albums', '{0}'.format(from_song['file_id']))
        a_orig_album = soup.new_tag('a', href=orig_album_file_path)
        a_orig_album.string = from_song['name']
        a_orig_album.string.wrap(soup.new_tag('i'))

        # Construct the string content of the list element including
        # information about the original song/album, a comment that the
        # song is an instrumental song if that applies, and a comment
        # that the song was sung by someone else if that applies
        li.string = ('{0} (appeared on {1}{2}){3}'
                     .format(a_song, a_orig_album, instrumental, sung_by))
    else:

        # Construct the string content of the list element including a
        # comment that the song is an instrumental song if that applies,
        # and a comment that the song was sung by someone else if that
        # applies
        li.string = '{0}{1}{2}'.format(song_name, instrumental, sung_by)
        li.string.wrap(a_song)
        
    # Italicize/gray out song entries if they do not contain lyrics
    if instrumental:
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
    """

    ol = soup.new_tag('ol')
    if sides_dict:
        for side in sides_dict:
            side_div = soup.new_tag('div')
            side_div.string = "Side {0}".format(side)
            ol.append(side_div)
            ol.append(soup.new_tag('p'))
            inner_ol = soup.new_tag('ol')
            first, last = sides_dict[side].split('-')
            for index, song in enumerate(songs):
                try:
                    if index + 1 in range(int(first), int(last) + 1):
                        inner_ol.append(generate_song_list_element(song, songs[song]))
                    if int(last) == index + 1:
                        break
                except TypeError as e:
                    raise ValueError('The "sides" attribute contains invalid '
                                     'song indices: {0}.'.format(sides_dict[side]))
            ol.append(inner_ol)
            ol.append(soup.new_tag('p'))
    else:
        for song in songs:
            ol.append(generate_song_list_element(song, songs[song]))
    
    return ol


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
    index_heading.string.wrap(soup.new_tag('a', href=albums_index_html_file_path))
    index_body.append(index_heading)

    # Add in ordered list element for all albums
    index_ol = soup.new_tag('ol')
    for album in albums:
        album_html_file_name = '{}.html'.format(albums[album]['attrs']['file_id'])
        album_html_file_path = join(site_url, 'albums', album_html_file_name)
        year = albums[album]['attrs']['release_date'].split()[-1]
        li = soup.new_tag('li')
        li.string = '{0} ({1})'.format(album, year)
        li.string.wrap(soup.new_tag('a', href=album_html_file_path))
        index_ol.append(li)
    index_body.append(index_ol)

    # Add in "Home" link
    div = soup.new_tag('div')
    div.string = 'Home'
    div.string.wrap(soup.new_tag('a', href=join(site_url, index_html_file_name)))
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

    # Make HTML element for albums index page
    html = soup.new_tag('html')

    # Generate body for albums page
    body = soup.new_tag('body')

    # Add in elements for the heading
    heading = soup.new_tag('h1')
    heading.string = name
    body.append(heading)

    # Add in the album attributes, including a picture of the album
    attrs_div = soup.new_tag('div')
    image_file_path = join(site_url, 'resources', 'images', attrs['image_file_name'])
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
    body.append(attrs_div)

    # Add in an ordered list element for all songs (or several ordered
    # lists for each side, disc, etc.)
    # NOTE: Deal with the possibility of a 'discs' attribute in addition
    # to the 'sides' attribute
    body.append(generate_song_list(songs, attrs.get('sides', None)))

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
        if not song_attrs.get('from'):
            htmlify_song(song, song_attrs['file_id'],
                         instrumental=song_attrs.get('instrumental'))

        # Add song text to the `song_texts`/`unique_song_texts` lists
        if make_downloads and not song_attrs.get('instrumental'):

            input_path = join(txt_dir, '{0}.txt'.format(song_attrs['file_id']))
            song_text = remove_annotations(standardize_quotes(open(input_path).read()).strip())
            song_texts.append(song_text)
            unique_song_texts.add(song_text)


def htmlify_song(name: str, song_id: str, instrumental: bool = False) -> None:
    """
    Read in a raw text file containing lyrics and output an HTML file
    (unless the song is an instrumental and contains no lyrics).

    If the song is an instrumental, do not try to read in the raw text
    file (as there will be none) and instead just write an HTML file
    that includes only the heading content and the text
    "(Instrumental)".

    :param name: song name
    :type name: str
    :param song_id: file ID
    :type song_id: str
    :param instrumental: whether or not the song is an instrumental
                         (default: False)
    :type instrumental: bool

    :returns: None
    :rtype: None
    """

    input_path = join(txt_dir, '{0}.txt'.format(song_id))
    html_file_name = '{0}.html'.format(song_id)
    html_output_path = join(html_dir, html_file_name)
    html_url = join(song_html_url, html_file_name)
    sys.stderr.write('HTMLifying {}...\n'.format(name))

    # Make BeautifulSoup object
    html = soup.new_tag('html')

    # Title
    heading = soup.new_tag('h1')
    heading.string = name
    html.append(heading)

    # Body element
    body = soup.new_tag('body')

    # If the song is an instrumental, forgo any text processing and
    # simply write a file that contains a message saying the song is an
    # instrumental
    if instrumental:
        div = soup.new_tag('div')
        p_elem = soup.new_tag('p')
        p_elem.string = "(Instrumental)"
        p_elem.string.wrap(soup.new_tag('i'))
        div.append(p_elem)
        body.append(div)

        # Put body in HTML element
        html.append(body)

        # Write out "prettified" HTML to the output file
        with open(html_output_path, 'w') as html_output:
            html_output.write(clean_up_html(str(html)))
        
        return

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
    for paragraph in paragraphs:
        paragraph_elem = soup.new_tag('p')
        for line_elem in paragraph:

            # Create new `div` element to store the line
            div = soup.new_tag('div')

            # Check if line has annotations
            annotation_nums = ANNOTATION_MARK.findall(line_elem)
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
                    href = '{0}#{1}'.format(html_url, annotation_num)
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

        body.append(paragraph_elem)

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
        body.append(annotation_section)

    # Put body in HTML element
    html.append(body)

    # Write out "prettified" HTML to the output file
    with open(html_output_path, 'w') as html_output:
        html_output.write(clean_up_html(str(html)))


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

    # Write raw lyrics files (for downloading), if requested
    if make_downloads:
        sys.stderr.write('Generating the full lyrics download files...\n')
        write_big_lyrics_files()

    sys.stderr.write('Program complete.\n')


if __name__ == '__main__':
    main()
