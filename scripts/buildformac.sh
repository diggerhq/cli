cd src
pip3 install pyinstaller
pip3 install -r requirements.txt
pyinstaller --clean -y --dist ./dist/mac --workpath /tmp dg.spec
chmod +x dist/mac/dg