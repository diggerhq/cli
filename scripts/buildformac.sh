cd dg
pip3 install pyinstaller
pip3 install -r requirements.txt
pyinstaller --clean -y --dist ./dist/dg-mac --workpath /tmp dg.spec
chmod +x dist/dg-mac/dg