import unittest
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from dg import dg
from dg.dg import cli

# mocking objects
dg.api = MagicMock()
dg.auth.require_auth = MagicMock()
dg.fetch_github_token = MagicMock()
dg.prompt = MagicMock()
dg.report_async = MagicMock()
dg.update_digger_yaml = MagicMock()
dg.json = MagicMock()
dg.create_aws_profile = MagicMock()


class ClickTestMixin():
    def setUp(self):
        self.runner = CliRunner()

    def _invoke_click_command(self, command):
        self.runner = CliRunner()
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                cli,
                command,
                catch_exceptions=False
            )
        return result


class TestProject(ClickTestMixin, unittest.TestCase):

    def test_project_init(self):
        result = self._invoke_click_command(["project", "init"])
        assert not result.exception


class TestService(ClickTestMixin, unittest.TestCase):

    def test_service_add(self):
        result = self._invoke_click_command(["service", "add"])
        assert not result.exception

    def test_service_create(self):
        result = self._invoke_click_command(["service", "create"])
        assert not result.exception

@patch("dg.dg.get_project_settings")
class TestEnv(ClickTestMixin, unittest.TestCase):

    def test_env_list(self, get_project_settings):
        result = self._invoke_click_command(["env", "list"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "create", "prod"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "sync-tform", "prod"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "build"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "push"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "deploy"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "destroy"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "history"])
        assert not result.exception

    def test_env_create(self, get_project_settings):
        result = self._invoke_click_command(["env", "apply", "prod"])
        assert not result.exception


class TestAuth(ClickTestMixin, unittest.TestCase):
    def test_auth(self):
        result = self._invoke_click_command(["auth"])
        assert not result.exception


class TestCreate(ClickTestMixin, unittest.TestCase):
    def test_create(self):
        result = self._invoke_click_command(["create", "myfolder"])
        assert not result.exception

class TestLogs(ClickTestMixin, unittest.TestCase):
    @patch("dg.dg.get_project_settings")
    def test_logs(self, get_project_settings):
        result = self._invoke_click_command(["logs", "serviceName"])
        assert not result.exception


@patch("dg.dg.get_project_settings")
class TestWebapp(ClickTestMixin, unittest.TestCase):

    def test_logs(self, get_project_settings):
        result = self._invoke_click_command(["webapp", "create"])
        assert not result.exception

    def test_logs(self, get_project_settings):
        result = self._invoke_click_command(["webapp", "add"])
        assert not result.exception

@patch("dg.dg.get_project_settings")
class TestResource(ClickTestMixin, unittest.TestCase):

    def test_resouce_create(self, get_project_settings):
        result = self._invoke_click_command(["resource", "create", "database"])
        assert not result.exception



if __name__ == '__main__':
    unittest.main()
