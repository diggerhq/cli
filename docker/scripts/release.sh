pyinstaller -y dg.spec
mkdir -p /dist
cp -r dist/* /dist
