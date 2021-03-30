
def parse_env_config_options(config : list):
    configOptions = {}
    for configOption in config:
        if configOption.find("=") < 0:
            Bcolors.error(f"each config should be of form key=val, found: {configOption}")
            sys.exit(-1)
        key,val = configOption.split("=")
        # parse boolean inputs correctly
        if val.lower() == "true" or val.lower() == "false":
            val = (val.lower() == "true")
        configOptions[key] = val
    return configOptions