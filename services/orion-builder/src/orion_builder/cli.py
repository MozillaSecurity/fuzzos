# coding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""CLI functions for Orion builder"""
from argparse import ArgumentParser
from locale import LC_ALL, setlocale
from logging import DEBUG, INFO, WARN, basicConfig, getLogger
from os import getenv


def configure_logging(level=INFO):
    """Configure a log handler.

    Arguments:
        level (int): Log verbosity constant from the `logging` module.

    Returns:
        None
    """
    setlocale(LC_ALL, "")
    basicConfig(level=level)
    if level == DEBUG:
        # no need to ever see lower than INFO for third-parties
        getLogger("taskcluster").setLevel(INFO)
        getLogger("urllib3").setLevel(INFO)


class BaseArgs:
    def __init__(self):
        self.parser = ArgumentParser()
        log_levels = self.parser.add_mutually_exclusive_group()
        log_levels.add_argument(
            "--quiet",
            "-q",
            dest="log_level",
            action="store_const",
            const=WARN,
            help="Show less logging output.",
        )
        log_levels.add_argument(
            "--verbose",
            "-v",
            dest="log_level",
            action="store_const",
            const=DEBUG,
            help="Show more logging output.",
        )

        self.parser.set_defaults(
            log_level=INFO,
        )

    @classmethod
    def parse_args(cls, argv=None):
        """Parse command-line arguments.

        Arguments:
            argv (list(str) or None): Argument list, or sys.argv if None.

        Returns:
            argparse.Namespace: parsed result
        """
        self = cls()
        result = self.parser.parse_args(argv)
        self.sanity_check(result)
        return result

    def sanity_check(self, args):
        pass


class CommonArgs(BaseArgs):
    """Parser for common command-line arguments."""

    def __init__(self):
        super().__init__()
        self.parser.add_argument(
            "--git-repository",
            default=getenv("GIT_REPOSITORY"),
            help="Repository holding the build context. (default: GIT_REPOSITORY)",
        )
        self.parser.add_argument(
            "--git-revision",
            default=getenv("GIT_REVISION"),
            help="Commit to clone the repository at. (default: GIT_REVISION)",
        )
        self.parser.add_argument(
            "--registry-secret",
            dest="secret",
            default=getenv("TASKCLUSTER_SECRET"),
            help="Credentials to login to Docker registry",
        )
        self.parser.add_argument(
            "--task-id",
            default=getenv("TASK_ID"),
            help="Taskcluster task ID for retrieving artifacts",
        )

        self.parser.set_defaults(
            cache=None,
            config=None,
            target=None,
        )

    def sanity_check(self, args):
        if args.git_repository is None:
            self.parser.error("--git-repository (or GIT_REPOSITORY) is required!")

        if args.git_revision is None:
            self.parser.error("--git-revision (or GIT_REVISION) is required!")
