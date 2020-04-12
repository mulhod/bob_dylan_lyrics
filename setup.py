from setuptools import setup, find_packages

def readme():
    return open('README.md').read()

def reqs():
    with open('requirements.txt') as f:
        return f.read().splitlines()

setup(name='bob_dylan_lyrics',
      description='Repository of Bob Dylan lyrics project. The aim is not '
                  'only to provide all of the lyrics, but to make sure the '
                  'lyrics are correct and also to supply the lyrics with '
                  'interpretations and punctuation (which they often lack '
                  'elsewhere).',
      url='https://github.com/mulhod/bob_dylan_lyrics',
      long_description=readme(),
      version='0.1',
      author='Matt Mulholland',
      author_email='mulhodm@gmail.com',
      include_package_data=True,
      install_requires=reqs(),
      packages=find_packages(),
      entry_points={'console_scripts':
                        ['htmlify = bob_dylan_lyrics.htmlify:main']},
      keywords='bob dylan lyrics',
      classifiers=['Intended Audience :: Science/Research',
                   'Intended Audience :: Developers',
                   'License :: ',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.3',
                   'Programming Language :: Python :: 3.2',
                   'Programming Language :: Python :: 3.1',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 2.6',
                   'Topic :: Scientific/Engineering',
                   'Operating System :: POSIX',
                   'Operating System :: Unix',
                   'Operating System :: MacOS'],
      zip_safe=False)
