# Installing `bob_dylan_lyrics`

- Use Conda, which can be installed by downloading a setup script from [here](http://conda.pydata.org/miniconda.html), making the script executable, and then running the script, and then adding the `bin` directory to the `PATH` environment variable. Typically, one specifies the `-b` option (for running in "batch" mode) and the `-p` prefix option for telling the script where to install Conda). For example, the following series of commands would install Conda on a 64-bit Linux installation, where `INSTALL_LOCATION` refers to the location in which to install Conda:
```
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod a+x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh -b -p $INSTALL_LOCATION/conda
```
- Afterwards, `$INSTALL_LOCATION/conda/bin` would have to be added to the `PATH` environment variable, i.e., by either running `export PATH=$PATH:$INSTALL_LOCATION/conda/bin` or by adding `$INSTALL_LOCATION/conda/bin` to the relevant line in your `.bashrc`, `.zshrc`, etc., file (and then sourcing it).
- Once Conda is installed, you can create a Conda environment named "dylan_lyrics", for example, with the following command: `conda create --yes -n dylan_lyrics python=3.5 entrypoints`
- Then, initialize the environment by running `source activate dylan_lyrics`
- If not using a virtual environment, just begin at the next step after installing the `entrypoints` package via `pip` or `conda`.
- After cloning this repository, change into its root directory and then run `pip` to install `bob_dylan_lyrics` and all required packages, e.g., `pip install .` (or `pip install -e .` if you want the package to be installed in editable mode).
