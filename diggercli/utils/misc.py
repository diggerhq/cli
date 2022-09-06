import os
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from diggercli.constants import DIGGER_CONFIG_FILE


def _retry_until(callable, max_retries=60, time_between_retries=10):
    current_retry_count = 1
    while True:
        if current_retry_count > max_retries:
            break
        callable()
        current_retry_count += 1
        time.sleep(time_between_retries)

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

# compute the variables along with overrides
def compute_env_vars_with_overrides(envVars: list, servicePk: int) -> dict:
    res = {}
    # expose env variables
    for var in envVars:
        if var["service"] is None:
            res[var["name"]] = var["value"]

    # Override service parameters
    for var in envVars:
        if var["service"] == servicePk:
            res[var["name"]] = var["value"]

    return res
