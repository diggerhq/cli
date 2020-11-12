
pip3 install pyinstaller
cd src
pyinstaller --clean -y --dist ./dist/mac --workpath /tmp dg.spec
chown -R --reference=. ./dist/mac