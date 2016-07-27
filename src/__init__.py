import re
from operator import itemgetter
from collections import OrderedDict
from os.path import dirname, realpath, join
from typing import Dict, List, Union, MutableMapping, Any

import cytoolz


SongFilesDictType = Dict[str,
                         List[Dict[str, Union[str, int, List[Dict[str, str]]]]]]
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
