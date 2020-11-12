
pip3 install pyinstaller
cd src
pyinstaller --clean -y --dist ./dist/mac --workpath /tmp $SPEC_FILE
chown -R --reference=. ./dist/mac