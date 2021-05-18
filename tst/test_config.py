import os
import unittest
import tempfile
from oyaml import load as yload, dump as ydump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from diggercli import dg
from unittest.mock import patch, MagicMock
from diggercli.utils.misc import (
    read_env_config_from_file,
    parse_env_config_options
)


class TestFileConfigOverride(unittest.TestCase):
    def test_without_file(self):
        options = {"a": "b"}
        expected = options
        found = read_env_config_from_file("staging", overrideOptions=options)
        self.assertDictEqual(expected, found)

    def test_with_file_and_no_overrides(self):
        config = {
            "default": {
                "a": "b",
                "x": "y",
            },
            "staging": {
                "x": "k",
            },
            "prod": {
                "x": "x",
            },

        }
        with tempfile.NamedTemporaryFile("w") as f:
            ydump(config, f)
            expected = {
                "a": "b",
                "x": "k"
            }
            found = read_env_config_from_file("staging", overrideOptions={}, filePath=f.name)
            self.assertDictEqual(expected, found)

            # testing the default case
            expected = {
                "a": "b",
                "x": "y",
            }
            found = read_env_config_from_file("newenv", overrideOptions={}, filePath=f.name)
            self.assertDictEqual(expected, found)

    def test_with_file_and_some_config_overrides(self):
        options = {"a": "a"}
        found = read_env_config_from_file("staging", overrideOptions={})
        config = {
            "default": {
                "a": "b",
                "x": "y",
            },
            "staging": {
                "x": "k",
            },
            "prod": {
                "x": "x",
            },

        }
        with tempfile.NamedTemporaryFile("w") as f:
            ydump(config, f)
            expected = {
                "a": "a",
                "x": "k"
            }
        
            found = read_env_config_from_file("staging", overrideOptions=options, filePath=f.name)
            self.assertDictEqual(expected, found)


class TestConfigFromCli(unittest.TestCase):

    def test_input_from_cli(self):
        expected = {
            "x": "y",
            "y": "z=123"
        }
        found = parse_env_config_options([
            "x=y",
            "y=z=123"
        ])
        self.assertDictEqual(expected, found)