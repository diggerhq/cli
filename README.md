

## Installation
- add an entry in your /etc/hosts to point digger.local -> 127.0.0.1
- create virtualenv with python version > 3.7
- `cp env/.env.example env/.env`
- update endpoint in env/.env file to `http://18.222.22.175:8000`
- pip install -r requirements.txt
- pip install --editable . 
- now test with `dg` -- you should see a help screen
- start from a blank folder


## Releasing

### On host:
- create a virtualenv for packaging
- pip install -r requirements.txt
- pip insall pyinstaller
- ` pyinstaller dg.spec`
- The released binary will be in dist/ folder

### Using docker:
-  docker build -t dg-release-debian -f docker/Dockerfile-release.debian .
- docker run -it -v $PWD/dist:/dist dg-release-debian
- The resulting binary will be in the dist/ folder, you can modify this by changing the first argument to `-v`

### With github actions:
Any tag which starts with vxxx will be built for linux and malk
A corresponding release will be created. In the releases tab https://github.com/diggerhq/cli/releases
You can download the release and upload to a pulic s3 bucket (we deploy to digger-releases/linux and digger-releases/darwin).
Update [homebrew](https://github.com/diggerhq/homebrew-tap/blob/master/Formula/dg.rb) and [notion page](https://www.notion.so/Quick-Start-deploy-a-service-d55adaf6bcb84399a3ab0633b19a2a45) with latest links
