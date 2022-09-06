import sys
import time
from halo import Halo as TrueHalo

def spin(t, msg, mode='dots'):
    spinner = Halo(text=msg, spinner=mode)
    spinner.start()
    time.sleep(t)
    spinner.stop()


class FakeHalo(TrueHalo):
    def start(self, **kwargs): 
        if self.text:
            print(self.text)

    def stop (self, **kwargs): pass


def Halo(**kwargs):

    if sys.stdout.isatty():
        return TrueHalo(**kwargs)
    else:
        return FakeHalo(**kwargs)


class SpinnerSegment:
    def __init__(self, text, spinner="dots", *args, **kwargs):
        self.spinner = Halo(text=text, spinner=spinner)
    
    def __enter__(self):
        self.spinner.start()

    def __exit__(self, *args, **kwargs):
        self.spinner.stop()


class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    OKPINK = '\033[35m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @classmethod
    def print(cls, msg, ctype):
        print(f"{ctype}{msg}{cls.ENDC}")

    @classmethod
    def header(cls, msg):
        cls.print(msg, cls.HEADER)

    @classmethod
    def okblue(cls, msg):
        cls.print(msg, cls.OKBLUE)

    @classmethod
    def okgreen(cls, msg):
        cls.print(msg, cls.OKGREEN)

    @classmethod
    def warn(cls, msg):
        cls.print(msg, cls.WARN)

    @classmethod
    def fail(cls, msg):
        cls.print(msg, cls.FAIL)

    @classmethod
    def endc(cls, msg):
        cls.print(msg, cls.ENDC)

    @classmethod
    def bold(cls, msg):
        cls.print(msg, cls.BOLD)

    @classmethod
    def underline(cls, msg):
        cls.print(msg, cls.UNDERLINE)