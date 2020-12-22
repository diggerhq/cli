# cd dg
python3 -m venv py3
source py3/bin/activate
pip install pyinstaller
pip install -r requirements.txt
pyinstaller --clean -y --dist ./dist/dg-mac --workpath /tmp dg.spec
chmod +x dist/dg-mac/dg