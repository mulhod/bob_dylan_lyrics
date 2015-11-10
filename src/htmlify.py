import sys
from bs4 import BeautifulSoup
from os.path import (join,
                     exists,
                     dirname)
from argparse import (ArgumentParser,
                      ArgumentDefaultsHelpFormatter)

# Paths
project_dir = dirname(dirname(__file__))
albums_dir = join(project_dir, 'albums')
songs_dir = join(project_dir, 'songs')
txt_dir = join(songs_dir, 'txt')
html_dir = join(songs_dir, 'html')
index_file_path = join(songs_dir, '.index')
index_html_file_name = 'index.html'
albums_index_html_file_name = 'albums.html'

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


def htmlify(albums):
    """
    Create HTML file for each album.

    :param albums: dictionary of album names/album HTML file names and
                   associated song dictionaries (which, in turn, have a
                   similar kind of contents)
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
    a = soup.new_tag('a')
    a.attrs['href'] = albums_index_html_file_name
    a.string = 'Albums'
    index_heading.insert(0, a)
    index_body.insert(0, index_heading)

    # Add in ordered list element for all albums
    index_ol = soup.new_tag('ol')
    for ol_ind, album in enumerate(albums):
        album_name = album[0]
        album_html_file_name = album[1]
        li = soup.new_tag('li')
        a = soup.new_tag('a')
        a.string = album_name
        a.attrs['href'] = join('albums', album_html_file_name)
        li.insert(0, a)
        index_ol.insert(ol_ind, li)
    index_body.insert(1, index_ol)

    # Add in "Home" link
    div = soup.new_tag('div')
    a_home = soup.new_tag('a')
    a_home.string = 'Home'
    a_home.attrs['href'] = index_html_file_name
    div.insert(0, a_home)
    index_body.insert(2, div)

    # Put body in HTML element
    index_html.insert(0, index_body)

    # Write new HTML file for albums index page
    with open(join(project_dir, albums_index_html_file_name), 'w') as albums_index:
        albums_index.write(index_html.prettify())

    # Generate pages for albums
    sys.stderr.write('HTMLifying the individual album pages...\n')
    for album, songs in albums.items():
        album_name = album[0]
        album_html_file_name = album[1]
        htmlify_album(album_name, album_html_file_name, songs)


def htmlify_album(name, file_name, songs):
    """
    Generate HTML pages for a particular album and its songs.

    :param name: name of the album
    :type name: str
    :param file_name: name of HTML file corresponding to the given
                      album
    :type file_name: str
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
    a = soup.new_tag('a')
    a.attrs['href'] = file_name
    a.string = name
    heading.insert(0, a)
    body.insert(0, heading)

    # Add in ordered list element for all songs
    ol = soup.new_tag('ol')
    for ol_ind, song in enumerate(songs.items()):
        song_name = song[0]
        song_file_id = song[1]
        li = soup.new_tag('li')
        a = soup.new_tag('a')
        a.string = song_name
        a.attrs['href'] = join('..', 'songs', 'html',
                               '{0}.html'.format(song_file_id))
        li.insert(0, a)
        ol.insert(ol_ind, li)
    body.insert(1, ol)

    # Add in links to "Home" and "Back"
    div = soup.new_tag('div')
    a_home = soup.new_tag('a')
    a_home.string = 'Home'
    a_home.attrs['href'] = join('..', index_html_file_name)
    div.insert(0, a_home)
    a_back = soup.new_tag('a')
    a_back.string = 'Back'
    a_back.attrs['href'] = join('..', albums_index_html_file_name)
    div.insert(1, a_back)
    body.insert(2, div)

    # Put body in HTML element
    html.insert(0, body)

    # Write new HTML file for albums index page
    with open(join(albums_dir, file_name), 'w') as album_file:
        album_file.write(html.prettify())

    # Generate HTML files for all of the songs
    for song, song_id in songs.items():
        htmlify_song(song, song_id, file_name)


def htmlify_song(name, song_id, album_file_name=None):
    """
    Read in a raw text file containing lyrics and output an HTML file.

    :param name: song name
    :type name: str
    :param song_id: file ID
    :type song_id: str
    :param album_file_name: containing album file name (if there is a
                            containing album)
    :type album_file_name: str or None

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
    html.insert(0, heading)

    # Process lines from raw lyrics file into different paragraph
    # elements
    body = soup.new_tag('body')
    song_lines = open(input_path).read().strip().split('\n')
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

    # Add in navigational links
    div = soup.new_tag('div')
    a_home = soup.new_tag('a')
    a_home.string = 'Home'
    a_home.attrs['href'] = join('..', '..', index_html_file_name)
    div.insert(0, a_home)
    if album_file_name:

        # Insert back/back to album navigational links only if the song
        # file has an associated album ID
        a_back = soup.new_tag('a')
        a_back.string = 'Back to album'
        a_back.attrs['href'] = join('..', '..', 'albums', album_file_name)
        div.insert(1, a_back)
        a_back_to_albums = soup.new_tag('a')
        a_back_to_albums.string = 'Back to albums'
        a_back_to_albums.attrs['href'] = join('..', '..',
                                              albums_index_html_file_name)
        div.insert(2, a_back_to_albums)
    current_body_ind = paragraph_ind + 1
    body.insert(current_body_ind, div)

    # Put body in HTML element
    html.insert(1, body)

    # Write out "prettified" HTML to the output file
    with open(html_output_path, 'w') as html_output:
        html_output.write(html.prettify())


def main():
    parser = \
        ArgumentParser(conflict_handler='resolve',
                       formatter_class=ArgumentDefaultsHelpFormatter,
                       description='Generates HTML files based largely on the'
                                   ' contents of the .index file and on the '
                                   'raw text files that contain the lyrics.')
    args = parser.parse_args()

    # Read in contents of .index file, constructing a dictionary of
    # albums and the associated songs, etc.
    sys.stderr.write('Reading .index file and building up index of albums and'
                     ' songs...\n')
    albums_dict = read_index()

    # Generate HTML files for albums, songs, etc.
    sys.stderr.write('Generating HTML files for the albums and songs...\n')
    htmlify(albums_dict)


if __name__ == '__main__':
    main()
