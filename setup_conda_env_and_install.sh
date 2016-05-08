#!/bin/zsh

# Note: having conda installed is a requirement (currently)

# Usage: ./setup_conda_env_and_install.sh

set -eu

ORIG_DIR=$(pwd)
THIS_DIR=$(dirname $(readlink -f $0))
cd ${THIS_DIR}

echo "Make sure that conda (miniconda) is installed before trying to set up" \
     "or else this script will fail..."

echo "Creating conda environment named \"dylan_lyrics\"..."
# Create environment first and force python=3.5
conda create --yes -n dylan_lyrics python=3.5
source activate dylan_lyrics

# And now run setup.py and install all of the packages we need
echo "Running setup.py and installing packages..."
python setup.py install
echo "Installation complete!"
echo "Now just run \"source activate dylan_lyrics\" any time you want to use" \
     "the virtual environment and \"source deactivate\" when you want to" \
     "leave the virtual environment."
