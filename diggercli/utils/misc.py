import os
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from diggercli.constants import DIGGER_CONFIG_FILE


def read_env_config_from_file(environmentName, overrideOptions={}, filePath=DIGGER_CONFIG_FILE):
    if not os.path.exists(filePath):
        return overrideOptions
    file = open(filePath)
    configOptions = yload(file, Loader=Loader)
    file.close()
    options = configOptions.get("default", {})
    environmentOptions = configOptions.get(environmentName, {})
    options.update(environmentOptions)
    options.update(overrideOptions)
    return options


def parse_env_config_options(config : list):
    configOptions = {}
    for configOption in config:
        if configOption.find("=") < 0:
            Bcolors.error(f"each config should be of form key=val, found: {configOption}")
            sys.exit(-1)
        key,val = configOption.split("=", 1)
        # parse boolean inputs correctly
        if val.lower() == "true" or val.lower() == "false":
            val = (val.lower() == "true")
        configOptions[key] = val
    return configOptions
