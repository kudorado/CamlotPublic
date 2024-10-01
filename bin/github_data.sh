# commit to csv_data
#!/usr/bin/env bash

URL=https://github.com/kudorado/CamlotPublic.git
FOLDER=vietlott-data
DATA_FOLDER=data
USER="Kudorado"
EMAIl="tmtudev@gmail.com"

# generate data file
echo "pwd $(pwd)"

export PYTHONPATH="src"
export LOGURU_LEVEL="INFO"

python src/vietlott/cli/crawl.py keno

python src/render_readme.py

#if [[ ! -d "$FOLDER" ]] ; then
#  git clone $URL $FOLDER
#fi

#cp -r $DATA_FOLDER $FOLDER/

#cd $FOLDER
#git pull

# commit and push
git config user.name "\'$USER\'"
git config user.email "\'$EMAIl\'"
git status
git add $DATA_FOLDER
git add readme.md
git commit -m "update data @ `date +%Y-%m-%d\ %H:%M:%S`"
git push
