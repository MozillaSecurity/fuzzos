# coding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Scheduler for Orion tasks"""
from logging import getLogger

from taskcluster.exceptions import TaskclusterFailure
from taskcluster.utils import slugId, stringDate

from . import ARTIFACTS_EXPIRE
from . import DEADLINE
from . import WORKER_TYPE
from . import PROVISIONER_ID
from . import MAX_RUN_TIME
from . import OWNER_EMAIL
from . import SOURCE_URL
from . import Taskcluster
from .git import GithubEvent
from .orion import Services


LOG = getLogger(__name__)


class Scheduler:
    def __init__(self, github_event, now, task_group, docker_secret, push_branch):
        self.github_event = github_event
        self.now = now
        self.task_group = task_group
        self.docker_secret = docker_secret
        self.push_branch = push_branch
        self.services = Services(self.github_event.repo.path)

    def mark_services_for_rebuild(self):
        """Check for services that need to be rebuilt.
        These will have their `dirty` attribute set, which is used to create tasks.

        Returns:
            None
        """
        if "/force-rebuild" in self.github_event.commit_message:
            LOG.info("/force-rebuild detected, all services will be marked dirty")
            for service in self.services.values():
                service.dirty = True
        else:
            self.services.mark_changed_dirty(self.github_event.list_changed_paths())

    def create_tasks(self):
        should_push = self.github_event.branch == self.push_branch
        queue = Taskcluster.get_service("queue")
        service_build_tasks = {service: slugId() for service in self.services}
        build_tasks_created = 0
        push_tasks_created = 0
        if not should_push:
            LOG.info(
                "Not pushing to Docker Hub (branch is %s, only push %s)",
                self.github_event.branch,
                self.push_branch,
            )
        for service in self.services.values():
            if self.github_event.pull_request is not None:
                build_index = (
                    f"index.project.fuzzing.orion.{service.name}"
                    f".pull_request.{self.github_event.pull_request}"
                )
            else:
                build_index = (
                    f"index.project.fuzzing.orion.{service.name}"
                    f".{self.github_event.branch}"
                )
            if not service.dirty:
                LOG.info("service %s doesn't need to be rebuilt", service.name)
                continue
            dirty_dep_tasks = [
                service_build_tasks[dep]
                for dep in service.service_deps
                if self.services[dep].dirty
            ]
            build_task = {
                "taskGroupId": self.task_group,
                "dependencies": dirty_dep_tasks,
                "created": stringDate(self.now),
                "deadline": stringDate(self.now + DEADLINE),
                "provisionerId": PROVISIONER_ID,
                "workerType": WORKER_TYPE,
                "payload": {
                    "artifacts": {
                        f"public/{service.name}.tar": {
                            "expires": stringDate(self.now + ARTIFACTS_EXPIRE),
                            "path": "/image.tar",
                            "type": "file",
                        },
                    },
                    "command": [
                        "build.sh",
                    ],
                    "env": {
                        "IMAGE_NAME": service.name,
                        "DOCKERFILE": str(
                            service.dockerfile.relative_to(service.context)
                        ),
                        "ARCHIVE_PATH": "/image.tar",
                        "GIT_REPOSITORY": self.github_event.clone_url,
                        "GIT_REVISION": self.github_event.commit,
                        "LOAD_DEPS": "1" if dirty_dep_tasks else "0",
                    },
                    "features": {"privileged": True},
                    "image": "mozillasecurity/taskboot:latest",
                    "maxRunTime": MAX_RUN_TIME.total_seconds(),
                },
                "routes": [
                    (
                        f"index.project.fuzzing.orion.{service.name}"
                        f".rev.{self.github_event.commit}"
                    ),
                    build_index,
                ],
                "scopes": [
                    "docker-worker:capability:privileged",
                    "queue:route:index.project.fuzzing.orion.*",
                ],
                "metadata": {
                    "description": f"Build the docker image for {service.name} tasks",
                    "name": f"Orion {service.name} docker build",
                    "owner": OWNER_EMAIL,
                    "source": SOURCE_URL,
                },
            }
            task_id = service_build_tasks[service.name]
            LOG.info("Creating task %s: %s", task_id, build_task["metadata"]["name"])
            try:
                queue.createTask(task_id, build_task)
            except TaskclusterFailure as exc:  # pragma: no cover
                LOG.error("Error creating build task: %s", exc)
                raise
            build_tasks_created += 1
            if not should_push:
                continue
            push_task = {
                "taskGroupId": self.task_group,
                "dependencies": [service_build_tasks[service.name]],
                "created": stringDate(self.now),
                "deadline": stringDate(self.now + DEADLINE),
                "provisionerId": PROVISIONER_ID,
                "workerType": WORKER_TYPE,
                "payload": {
                    "command": [
                        "taskboot",
                        "push-artifact",
                    ],
                    "env": {
                        "TASKCLUSTER_SECRET": self.docker_secret,
                    },
                    "features": {"taskclusterProxy": True},
                    "image": "mozillasecurity/taskboot:latest",
                    "maxRunTime": MAX_RUN_TIME.total_seconds(),
                },
                "scopes": [
                    f"secrets:get:{self.docker_secret}",
                ],
                "metadata": {
                    "description": (
                        f"Publish the docker image for {service.name} tasks"
                    ),
                    "name": f"Orion {service.name} docker push",
                    "owner": OWNER_EMAIL,
                    "source": SOURCE_URL,
                },
            }
            task_id = slugId()
            LOG.info("Creating task %s: %s", task_id, push_task["metadata"]["name"])
            try:
                queue.createTask(task_id, push_task)
            except TaskclusterFailure as exc:  # pragma: no cover
                LOG.error("Error creating build task: %s", exc)
                raise
            push_tasks_created += 1
        LOG.info(
            "Created %d build tasks and %d push tasks",
            build_tasks_created,
            push_tasks_created,
        )

    @classmethod
    def main(cls, args):
        """Decision procedure.

        Arguments:
            args (argparse.Namespace): Arguments as returned by `parse_args()`

        Returns:
            int: Shell return code.
        """
        # get the github event & repo
        evt = GithubEvent.from_taskcluster(args.github_action, args.github_event)
        try:

            # create the scheduler
            sched = cls(
                evt,
                args.now,
                args.task_group,
                args.docker_hub_secret,
                args.push_branch,
            )

            sched.mark_services_for_rebuild()

            # schedule tasks
            sched.create_tasks()
        finally:
            evt.cleanup()

        return 0
