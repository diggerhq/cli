import unittest
import os
from unittest.mock import patch, MagicMock

from diggercli import dg
from diggercli.validators import (
    project_name_validate,
    env_name_validate
)


# TODO: parametarise tests
class TestProjectValidator(unittest.TestCase):

    def test_project_name_valid(self):
        project_name_validate("iamvalid")

    def test_project_name_valid2(self):
        project_name_validate("exactlyten")

    def test_project_name_valid3(self):
        project_name_validate("hiphen-ok")

    def test_project_name_valid4(self):
        project_name_validate("0123numsok")

    def test_project_name_invalid(self):
        with self.assertRaises(ValueError) as context:
            project_name_validate("cant contain spaces")

    def test_project_name_invalid2(self):
        with self.assertRaises(ValueError) as context:
            project_name_validate("elevenexact")

    def test_project_name_invalid3(self):
        with self.assertRaises(ValueError) as context:
            project_name_validate("@!@£sdf")


# TODO: parametarise tests
class TestEnvironmentValidator(unittest.TestCase):

    def test_project_name_valid(self):
        env_name_validate("iamvalid")

    def test_project_name_valid2(self):
        env_name_validate("exactlyten")

    def test_project_name_valid3(self):
        env_name_validate("hiphen-ok")

    def test_project_name_valid4(self):
        env_name_validate("0123numsok")

    def test_project_name_invalid(self):
        with self.assertRaises(ValueError) as context:
            env_name_validate("cant contain spaces")

    def test_project_name_invalid2(self):
        with self.assertRaises(ValueError) as context:
            env_name_validate("elevenexact")

    def test_project_name_invalid3(self):
        with self.assertRaises(ValueError) as context:
            env_name_validate("@!@£sdf")

