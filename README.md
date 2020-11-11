

## Installation

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
