

# fetch latest changes to upstream

```
# git remote add upstream https://github.com/arrowtype/recursive-code-config.git
git fetch upstream
git pull upstream main
```


# setup one time

```
python3.11 -m venv venv                # make a virtual environment called "venv"
source venv/bin/activate            # activate the virtual environment
pip install -r requirements.txt     # install dependencies
```

# build the font

```
bash
source venv/bin/activate        # activate the virtual environment if you haven’t already
python3.11 scripts/instantiate-code-fonts.py premade-configs/config.kg.yaml font-data/Recursive_VF_1.085.ttf
```
