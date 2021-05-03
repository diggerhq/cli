import os
import unittest
import tempfile
from diggercli import dg
from unittest.mock import patch, MagicMock

prompt_for_aws_keys_mock = MagicMock()
prompt_for_aws_keys_mock.return_value = {
    "aws_key": "input_user_key",
    "aws_secret": "input_user_secret" 
}
dg.prompt_for_aws_keys = prompt_for_aws_keys_mock

tmpdirname = tempfile.TemporaryDirectory()
dg.DIGGERHOME_PATH = tmpdirname.name
open(os.path.join(tmpdirname.name, "credentials"), "w").close()

def override_creds_file():
    global tmpdirname
    f = open(os.path.join(tmpdirname.name, "credentials"), "w")
    f.write("""
[project-environment]
aws_access_key_id = file_aws_key
aws_secret_access_key = file_aws_secret
""")
    f.close()

class TestAwsRetriveCredentials(unittest.TestCase):

    @patch("diggercli.dg.prompt_for_aws_keys")
    def test_retrieve_with_prompt(self, prompt_for_aws_keys):
        prompt_for_aws_keys.return_value = {
            "aws_key": "input_user_key",
            "aws_secret": "input_user_secret" 
        }
        credentials = dg.retreive_aws_creds("project", "environment", aws_key="aws_key", aws_secret="aws_secret", prompt=True)
        prompt_for_aws_keys.assert_called()
        self.assertEqual(credentials["aws_key"], "input_user_key")
        self.assertEqual(credentials["aws_secret"], "input_user_secret")

    def test_retrieve_with_key_override(self):
        credentials = dg.retreive_aws_creds("project", "environment", aws_key="aws_key", aws_secret="aws_secret", prompt=False)
        self.assertEqual(credentials["aws_key"], "aws_key")
        self.assertEqual(credentials["aws_secret"], "aws_secret")

    def test_retrieve_with_key_override_while_file_exists_returns_override(self):
        override_creds_file()
        credentials = dg.retreive_aws_creds("project", "environment", aws_key="aws_key2", aws_secret="aws_secret2", prompt=False)
        self.assertEqual(credentials["aws_key"], "aws_key2")
        self.assertEqual(credentials["aws_secret"], "aws_secret2")

    def test_retrieve_without_key_override(self):
        override_creds_file()
        credentials = dg.retreive_aws_creds("project", "environment", aws_key=None, aws_secret=None, prompt=False)
        self.assertEqual(credentials["aws_key"], "file_aws_key")
        self.assertEqual(credentials["aws_secret"], "file_aws_secret")



