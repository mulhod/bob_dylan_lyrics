import re
import sys
from json import loads
from os.path import (join,
                     exists,
                     dirname,
                     basename)
from collections import OrderedDict

from bs4 import BeautifulSoup
from argparse import (ArgumentParser,
                      ArgumentDefaultsHelpFormatter)

# Paths
project_dir = dirname(dirname(__file__))
albums_dir = join(project_dir, 'albums')
songs_dir = join(project_dir, 'songs')
index_file_path = join(project_dir, 'albums_and_songs_index.jsonlines')
txt_dir = join(songs_dir, 'txt')
html_dir = join(songs_dir, 'html')
index_html_file_name = 'index.html'
albums_index_html_file_name = 'albums.html'

# BeautifulSoup-related
soup = BeautifulSoup('', 'html.parser')

# Regular expression matching the expected annotation format
ANNOTATION = re.compile(r'\*\*([0-9]+)\*\*')

# Regular expressions for stylized double, single quotes
DOUBLE_QUOTES = re.compile(r'“|”')
SINGLE_QUOTES = re.compile(r'‘')

# BeautifulSoup clean-up-related regular expressions
BS_CLEANUP1 = re.compile(r'&gt;')
BS_CLEANUP2 = re.compile(r'&lt;')


def remove_annotations(line):
    """
    Remove all annotations from a line of text.

    :param line: input line
    :type line: str

    :returns: output line
    :rtype: str
    """

    return ANNOTATION.sub('', line)


def replace_funky_quotes(text):
    """
    Replace all single/double stylized quotes with their unstylized
    counterparts.

    :param text: input text
    :type text: str

    :returns: output text
    :rtype: str
    """

    return SINGLE_QUOTES.sub(r"'", DOUBLE_QUOTES.sub(r'"', text))


def clean_up_html(html):
    """
    Clean up HTML generated via BeautifulSoup by converting
    "&lt;"/"&gt;" character sequences to "<"/">".

    :param html: input HTML
    :type html: str

    :returns: output HTML
    :rtype: str
    """

    return BS_CLEANUP2.sub(r'<', BS_CLEANUP1.sub(r'>', html))


def find_annotation_indices(line, annotations):
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


def read_songs_index():
    """
    Read .songs_index file and make dictionary representation.

    :returns: albums dictionary
    :rtype: dict

    :raises: ValueError
    """

    albums = OrderedDict()
    for album_or_song_dict in (loads(line.strip('\n')) for line
                               in open(index_file_path)
                               if not line.startswith('#') and line.strip('\n')):

        if album_or_song_dict['type'] == 'album':

            attrs = album_or_song_dict['metadata']
            songs = attrs['songs']
            del attrs['songs']
            albums[attrs['name']] = \
                dict(attrs=attrs,
                     songs=OrderedDict((song_id, song_dict['file_id'])
                                       for song_id, song_dict
                                       in sorted(songs.items(),
                                                 key=lambda x: x[1]['index'])))

        elif album_or_song_dict['type'] == 'song':

            # Define the actions to take when an entry only contains a
            # single song (when this comes up eventually)
            pass

        else:
            raise ValueError('Encountered a JSON object whose "type" '
                             'attribute is neither "album" nor "song".')

    if not albums:
        raise ValueError('No albums found in .songs_index file!')

    return albums


def htmlify_everything(albums):
    """
    Create HTML files for the albums index page, each album, and each
    song.

    :param albums: dictionary of album names mapped to tuples
                   containing an album attribute dictionary, including
                   attributes such as the HTML file name, the release
                   date, etc., and a song dictionary
    :type albums: dict

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
        year = albums[album]['attrs']['release_date'].split()[-1]
        li = soup.new_tag('li')
        li.string = '{0} ({1})'.format(album, year)
        li.string.wrap(soup.new_tag('a', href=join('albums', album_html_file_name)))
        index_ol.append(li)
    index_body.append(index_ol)

    # Add in "Home" link
    div = soup.new_tag('div')
    div.string = 'Home'
    div.string.wrap(soup.new_tag('a', href=index_html_file_name))
    index_body.append(div)

    # Put body in HTML element
    index_html.append(index_body)

    # Write new HTML file for albums index page
    with open(join(project_dir, albums_index_html_file_name), 'w') as albums_index:
        albums_index.write(index_html.prettify(formatter="html"))

    # Generate pages for albums
    sys.stderr.write('HTMLifying the individual album pages...\n')
    for album, attrs_songs in albums.items():
        htmlify_album(album, attrs_songs['attrs'], attrs_songs['songs'])


def htmlify_album(name, attrs, songs):
    """
    Generate HTML pages for a particular album and its songs.

    :param name: name of the album
    :type name: str
    :param attrs: dictionary of album attributes, including the name of
                  the HTML file corresponding to the given album
    :type attrs: str
    :param songs: dictionary of song names mapped to song IDs
    :type songs: dict

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
    image = soup.new_tag('img', src=join('resources', 'images',
                                         attrs['image_file_name']))
    attrs_div.append(image)
    release_div = soup.new_tag('div')
    release_div.string = 'Released: {0}'.format(attrs['release_date'])
    attrs_div.append(release_div)
    length_div = soup.new_tag('div')
    length_div.string = 'Length: {0}'.format(attrs['length'])
    attrs_div.append(length_div)
    producers_string = attrs['producers']
    producers_string_template = \
        ('Producer{0}: {1}'
         .format('' if len(producers_string.split(', ')) == 1 else '(s)', '{0}'))
    producers_div = soup.new_tag('div')
    producers_div.string = producers_string_template.format(producers_string)
    attrs_div.append(producers_div)
    label_div = soup.new_tag('div')
    label_div.string = 'Label: {0}'.format(attrs['label'])
    attrs_div.append(label_div)
    body.append(attrs_div)

    # Add in ordered list element for all songs
    ol = soup.new_tag('ol')
    for song in songs.items():
        song_name = song[0]
        song_file_id = song[1]
        li = soup.new_tag('li')
        li.string = song_name
        li.string.wrap(soup.new_tag('a',
                                    href=join('songs', 'html',
                                              '{0}.html'.format(song_file_id))))
        ol.append(li)
    body.append(ol)

    # Put body in HTML element
    html.append(body)

    # Write new HTML file for albums index page
    with open(join(albums_dir,
                   '{}.html'.format(attrs['file_id'])), 'w') as album_file:
        album_file.write(html.prettify(formatter="html"))

    # Generate HTML files for all of the songs
    for song, song_id in songs.items():
        htmlify_song(song, song_id)


def htmlify_song(name, song_id):
    """
    Read in a raw text file containing lyrics and output an HTML file.

    :param name: song name
    :type name: str
    :param song_id: file ID
    :type song_id: str

    :returns: None
    :rtype: None
    """

    input_path = join(txt_dir, '{0}.txt'.format(song_id))
    html_output_path = join(html_dir, '{0}.html'.format(song_id))
    sys.stderr.write('HTMLifying {}...\n'.format(name))

    # Make BeautifulSoup object
    html = soup.new_tag('html')

    # Title
    heading = soup.new_tag('h1')
    heading.string = name
    html.append(heading)

    # Process lines from raw lyrics file into different paragraph
    # elements
    body = soup.new_tag('body')
    song_lines = replace_funky_quotes(open(input_path).read()).strip().split('\n')
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
            annotation_nums = ANNOTATION.findall(line_elem)
            if annotation_nums:

                # Get indices for the annotations in the given line
                annotation_inds = find_annotation_indices(line_elem,
                                                          annotation_nums)

                # Remove annotations from the line
                line_elem = remove_annotations(line_elem)

                # Copy the contents of the line (after removing the
                # annotations) into the `div` element
                div.string = line_elem

                # Iterate over the annotations, generating anchor
                # elements that link the annotation to the note at the
                # bottom of the page
                for i, annotation_num in enumerate(annotation_nums):
                    a = soup.new_tag('a',
                                     href='#'.join([basename(html_output_path),
                                                    annotation_num]))
                    a.string = annotation_num
                    a.string.wrap(soup.new_tag('sup'))

                    # Insert the anchor element into the `div` element
                    # at the appropriate location
                    ind = annotation_inds[i]
                    if ind == len(div.string):
                        div.string.replace_with('{0}{1}'
                                                .format(div.string, str(a)))
                    else:
                        (div.string
                         .replace_with('{0}{1}{2}'
                                       .format(div.string[:ind], str(a),
                                               div.string[ind:])))

                        # After putting annotations back into the
                        # contents of the `div`, the indices of the
                        # annotations after will necessarily change as
                        # they will be pushed back by the length of the
                        # string that is being added
                        for j in range(len(annotation_inds)):
                            if j > i:
                                annotation_inds[j] = (annotation_inds[j]
                                                      + len(a.string))
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


def main():
    parser = \
        ArgumentParser(conflict_handler='resolve',
                       formatter_class=ArgumentDefaultsHelpFormatter,
                       description='Generates HTML files based largely on the'
                                   ' contents of the .songs_index file and on'
                                   ' the raw text files that contain the '
                                   'lyrics.')
    args = parser.parse_args()

    # Read in contents of .songs_index file, constructing a dictionary
    # of albums and the associated songs, etc.
    sys.stderr.write('Reading .songs_index file and building up index of '
                     'albums and songs...\n')
    albums_dict = read_songs_index()

    # Generate HTML files for albums, songs, etc.
    sys.stderr.write('Generating HTML files for the albums and songs...\n')
    htmlify_everything(albums_dict)


if __name__ == '__main__':
    main()
