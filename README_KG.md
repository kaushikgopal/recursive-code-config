# fetch latest changes to upstream

```
# git remote add upstream https://github.com/arrowtype/recursive-code-config.git
git fetch upstream
git pull upstream main
```

# setup one time

```
pyenv local 3.11.8
python -m venv venv                # make a virtual environment called "venv"
source venv/bin/activate            # activate the virtual environment
pip install -r requirements.txt     # install dependencies
```

# build the font

```
bash
source venv/bin/activate        # activate the virtual environment if you haven’t already

# remove old installed fonts (macOS only; adjust for your OS)
trash /Users/kg/Library/Fonts/RecursiveKG*; trash fonts/RecursiveKG*

python scripts/instantiate-code-fonts.py premade-configs/config.kg.yaml font-data/Recursive_VF_1.085.ttf
```
