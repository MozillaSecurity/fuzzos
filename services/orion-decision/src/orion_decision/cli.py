# coding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""CLI for Orion scheduler"""
import sys
from argparse import ArgumentParser
from datetime import datetime
from locale import LC_ALL, setlocale
from logging import DEBUG, INFO, WARN, basicConfig, getLogger
from os import getenv
from pathlib import Path

from dateutil.parser import isoparse
from yaml import safe_load as yaml_load

from .git import GitRepo
from .orion import Services
from .scheduler import Scheduler


def configure_logging(level=INFO):
    """Configure a log handler.

    Arguments:
        level (int): Log verbosity constant from the `logging` module.

    Returns:
        None
    """
    setlocale(LC_ALL, "")
    basicConfig(format="[%(levelname).1s] %(message)s", level=level)
    if level == DEBUG:
        # no need to ever see lower than INFO for third-parties
        getLogger("taskcluster").setLevel(INFO)
        getLogger("urllib3").setLevel(INFO)


def _define_logging_args(parser):
    log_levels = parser.add_mutually_exclusive_group()
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
    parser.set_defaults(
        log_level=INFO,
    )


def parse_args(argv=None):
    """Parse command-line arguments.

    Arguments:
        argv (list(str) or None): Argument list, or sys.argv if None.

    Returns:
        argparse.Namespace: parsed result
    """
    parser = ArgumentParser()
    _define_logging_args(parser)
    parser.add_argument(
        "--task-group",
        default=getenv("TASK_ID"),
        help="Create tasks in this task group (default: TASK_ID).",
    )
    parser.add_argument(
        "--push-branch",
        default=getenv("PUSH_BRANCH", "master"),
        help="Push to Docker Hub if push event is on this branch " "(default: master).",
    )
    parser.add_argument(
        "--docker-hub-secret",
        default=getenv("DOCKER_HUB_SECRET"),
        help="Taskcluster secret holding Docker Hub credentials for push.",
    )
    parser.add_argument(
        "--github-event",
        default=getenv("GITHUB_EVENT", "{}"),
        type=yaml_load,
        help="The raw Github Webhook event.",
    )
    parser.add_argument(
        "--github-action",
        default=getenv("GITHUB_ACTION"),
        choices={"github-push", "github-pull-request", "github-release"},
        help="The event action that triggered this decision.",
    )
    parser.add_argument(
        "--now",
        default=getenv("TASKCLUSTER_NOW", datetime.utcnow().isoformat()),
        type=isoparse,
        help="Time reference to calculate task timestamps from ('now' according "
        "to Taskcluster).",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Do not queue tasks in Taskcluster, only calculate what would be done.",
    )

    result = parser.parse_args(argv)

    if result.github_action is None:
        parser.error("--github-action (or GITHUB_ACTION) is required!")

    if not result.github_event:
        parser.error("--github-event (or GITHUB_EVENT) is required!")

    return result


def parse_check_args(argv=None):
    """Parse command-line arguments for check.

    Arguments:
        argv (list(str) or None): Argument list, or sys.argv if None.

    Returns:
        argparse.Namespace: parsed result
    """
    parser = ArgumentParser()
    _define_logging_args(parser)
    parser.add_argument(
        "repo",
        type=Path,
        help="Orion repo root to scan for service files",
    )
    parser.add_argument(
        "changed",
        type=Path,
        nargs="*",
        help="Changed path(s)",
    )
    return parser.parse_args(argv)


def check():
    """Service definition check entrypoint."""
    args = parse_check_args()
    configure_logging(level=args.log_level)
    svcs = Services(GitRepo.from_existing(args.repo))
    svcs.mark_changed_dirty([args.repo / file for file in args.changed])
    sys.exit(0)


def main():
    """Decision entrypoint. Does not return."""
    args = parse_args()
    configure_logging(level=args.log_level)
    sys.exit(Scheduler.main(args))
