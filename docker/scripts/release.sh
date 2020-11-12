pyinstaller -y src/dg.spec
mkdir -p /dist
cp -r dist/* /dist
