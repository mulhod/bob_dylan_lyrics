import sys
from bs4 import BeautifulSoup
from os.path import (join,
                     exists,
                     dirname)
from argparse import (ArgumentParser,
                      ArgumentDefaultsHelpFormatter)

# Paths
project_dir = dirname(dirname(__file__))
songs_dir = join(project_dir, 'songs')
txt_dir = join(songs_dir, 'txt')
html_dir = join(songs_dir, 'html')
index_file_path = join(songs_dir, '.index')

# BeautifulSoup-related
soup = BeautifulSoup('', 'html.parser')

def read_index():
    """
    Read .index file and make dictionary representation.

    :returns: albums dictionary
    :rtype: dict

    :raises: ValueError
    """

    albums = {}
    i = 0
    lines = open(index_file_path).readlines()
    current_album = {}
    while i < len(lines):

        # Strip newlines off the end of the line
        line = lines[i].strip('\n')

        # Empty lines separate albums in .index
        if not line:
            i += 1
            continue

        # Lines that name an album begin unindented
        elif not line.startswith(' '):
            current_album = tuple(line.rsplit(', '))
            albums[current_album] = {}
            i += 1

        # Songs begin on indented lines
        else:
            song, song_id = line.strip().rsplit(', ', 1)
            albums[current_album][song] = song_id
            i += 1

    if not albums:
        raise ValueError('No albums found in .index file!')
    return albums


def htmlify(name, text_path, html_path):
    """
    Read in a raw text file containing lyrics and output an HTML file.

    :param name: song name
    :type name: str
    :param text_path: path to raw song file
    :type text_path: str
    :param html_path: path for output HTML file
    :type html_path: str

    :returns: None
    :rtype: None
    """

    sys.stderr.write('HTMLifying {}...\n'.format(text_path))

    # Make BeautifulSoup object
    html = soup.new_tag('html')

    # Title
    heading = soup.new_tag('h1')
    heading.string = name
    html.insert(0, heading)

    # Process lines from raw lyrics file into different paragraph
    # elements
    body = soup.new_tag('body')
    song_lines = open(text_path).read().strip().split('\n')
    paragraphs = []
    current_paragraph = []
    for ind, line in enumerate(song_lines):
        if line.strip():
            current_paragraph.append(line.strip())
            if len(song_lines) == ind + 1:
                paragraphs.append(current_paragraph)
                current_paragraph = []
        else:
            paragraphs.append(current_paragraph)
            current_paragraph = []

    # Add paragraph elements with sub-elements of type `div` to the
    # `body` element
    for paragraph_ind, paragraph in enumerate(paragraphs):
        paragraph_elem = soup.new_tag('p')
        div_ind = 0
        for line_elem in paragraph:
            div = soup.new_tag('div')
            div.string = line_elem
            paragraph_elem.insert(div_ind, div)
            div_ind += 1
        body.insert(paragraph_ind, paragraph_elem)
    html.insert(1, body)

    # Write out "prettified" HTML to the output file
    with open(html_path, 'w') as html_output:
        html_output.write(html.prettify())


def main():
    parser = \
        ArgumentParser(conflict_handler='resolve',
                       formatter_class=ArgumentDefaultsHelpFormatter,
                       description='Generates HTML files based on the raw text'
                                   ' files that contain lyrics. Will not '
                                   'replace HTML files if they already exist '
                                   '(unless the --force option is used).')
    parser.add_argument('-f', '--force',
                        help='Regenerate HTML files even if they already exist.',
                        action='store_true',
                        default=False)
    args = parser.parse_args()

    # Read in contents of .index file, constructing a dictionary of
    # albums and the associated songs, etc.
    albums_dict = read_index()

    # HTMLify song files if they haven't already been HTMLified
    for album in albums_dict:
        for song_name, song_id in albums_dict[album].items():

            # File paths
            txt_file_path = join(txt_dir, '{}.txt'.format(song_id))
            html_file_path = join(html_dir, '{}.html'.format(song_id))

            # Raise an exception if a text file is not found, which
            # should never be the case
            if not exists(txt_file_path):
                raise ValueError('File does not exist: {}'.format(txt_file_path))

            # Skip making HTML file if one already exists (unless
            # --force was used)
            if (exists(html_file_path)
                and not args.force):
                continue

            # HTMLify the text file
            htmlify(song_name, txt_file_path, html_file_path)


if __name__ == '__main__':
    main()
