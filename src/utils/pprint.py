from halo import Halo
import time

def spin(t, msg, mode='dots'):
    spinner = Halo(text=msg, spinner=mode)
    spinner.start()
    time.sleep(t)
    spinner.stop()
    
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