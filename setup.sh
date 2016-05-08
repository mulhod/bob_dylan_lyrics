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
source activate dylan_lyrics

# And now run setup.py and install all of the packages we need
echo "Running setup.py and installing packages..."
python3.4 setup.py install
echo "Installation complete!"