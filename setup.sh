#!/bin/zsh

# Note: having conda installed is a requirement (currently)

# Usage: ./setup.sh

set -eu

ORIG_DIR=$(pwd)
THIS_DIR=$(dirname $(readlink -f $0))
cd ${THIS_DIR}

echo "Make sure that conda (miniconda) is installed before trying to set up" \
     "or else this script will fail..."

echo "Creating conda environment..."
# Create environment first and force python=3.5 (for some reason, just adding
# python=3.5 to the list of packages in conda_requirements.txt does not work
# as it is not recognized as a valid package name)
conda create --yes -n dylan_lyrics python=3.5
# And now install all of the packages we need
source activate reviews
conda install --yes --file conda_requirements.txt
if [[ $? -gt 0 ]]; then
    
    echo "\"conda install --yes --file conda_requirements.txt\" failed." \
         "Exiting."
    cd ${ORIG_DIR}
    exit 1
    
fi
echo "Created \"dylan_lyrics\" environment successfully! To use environment," \
     "run \"source activate dylan_lyrics\". To get out of the environment," \
     "run \"source deactivate\"."

echo "Installing some extra packages with pip (since conda does not seem to" \
     "want to install them)..."
pip install argparse pudb
if [[ $? -gt 0 ]]; then
    
    echo "pip installation of langdetect and argparse failed. Exiting."
    cd ${ORIG_DIR}
    exit 1
    
fi

# Compile Cython modules
echo "Compiling Cython extensions..."
python3.4 setup.py install
echo "Package installed!"