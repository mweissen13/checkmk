#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""
This module implements generic functionality of the Check_MK backup
system. It is used to configure the site and system backup.
"""

from __future__ import annotations

import abc
import contextlib
import errno
import glob
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from io import TextIOWrapper
from pathlib import Path
from typing import cast, Final, Generic, TypedDict, TypeVar

from typing_extensions import assert_never

import cmk.utils.render as render
import cmk.utils.version as cmk_version
from cmk.utils.backup.config import Config as RawConfig
from cmk.utils.backup.type_defs import (
    JobConfig,
    LocalTargetParams,
    RawBackupInfo,
    ScheduleConfig,
    TargetConfig,
    TargetId,
)
from cmk.utils.paths import omd_root
from cmk.utils.plugin_registry import Registry
from cmk.utils.schedule import next_scheduled_time
from cmk.utils.site import omd_site

import cmk.gui.forms as forms
import cmk.gui.key_mgmt as key_mgmt
from cmk.gui.breadcrumb import Breadcrumb, make_simple_page_breadcrumb
from cmk.gui.exceptions import FinalizeRequest, HTTPRedirect, MKGeneralException, MKUserError
from cmk.gui.htmllib.generator import HTMLWriter
from cmk.gui.htmllib.header import make_header
from cmk.gui.htmllib.html import html
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.key_mgmt import Key
from cmk.gui.logged_in import user
from cmk.gui.main_menu import mega_menu_registry
from cmk.gui.page_menu import (
    make_simple_form_page_menu,
    make_simple_link,
    PageMenu,
    PageMenuDropdown,
    PageMenuEntry,
    PageMenuTopic,
)
from cmk.gui.table import table_element
from cmk.gui.type_defs import ActionResult
from cmk.gui.utils.flashed_messages import flash
from cmk.gui.utils.transaction_manager import transactions
from cmk.gui.utils.urls import (
    DocReference,
    make_confirm_link,
    makeactionuri,
    makeactionuri_contextless,
    makeuri_contextless,
)
from cmk.gui.utils.user_errors import user_errors
from cmk.gui.valuespec import (
    AbsoluteDirname,
    Alternative,
    CascadingDropdown,
    Checkbox,
    Dictionary,
    DropdownChoice,
    FixedValue,
    ID,
    ListOf,
    Password,
    SchedulePeriod,
    TextInput,
    Timeofday,
    ValueSpecText,
)

# .
#   .--Config--------------------------------------------------------------.
#   |                     ____             __ _                            |
#   |                    / ___|___  _ __  / _(_) __ _                      |
#   |                   | |   / _ \| '_ \| |_| |/ _` |                     |
#   |                   | |__| (_) | | | |  _| | (_| |                     |
#   |                    \____\___/|_| |_|_| |_|\__, |                     |
#   |                                           |___/                      |
#   +----------------------------------------------------------------------+
#   | Handling of the backup configuration files. This is used to handle   |
#   | either the global system config for the appliance and the site       |
#   | specific configuration of the site backup.                           |
#   '----------------------------------------------------------------------'


def mkbackup_path() -> Path:
    return omd_root / "bin/mkbackup"


def hostname() -> str:
    return socket.gethostname()


def is_canonical(directory: str) -> bool:  # type:ignore[no-untyped-def]
    if not directory.endswith("/"):
        directory += "/"
    return (
        os.path.isabs(directory)
        and os.path.commonprefix([os.path.realpath(directory) + "/", directory]) == directory
    )


class Config:
    def __init__(self, config: RawConfig) -> None:
        self._config = config
        self._cronjob_path = omd_root / "etc/cron.d/mkbackup"

    @classmethod
    def load(cls) -> Config:
        return cls(RawConfig.load())

    @property
    def jobs(self) -> dict[str, Job]:
        return {
            job_id: Job(
                job_id,
                job_config,
            )
            for job_id, job_config in self._config.site.jobs.items()
        }

    @property
    def site_targets(self) -> dict[TargetId, Target]:
        return {
            target_id: Target(
                target_id,
                target_config,
            )
            for target_id, target_config in self._config.site.targets.items()
        }

    @property
    def cma_system_targets(self) -> dict[TargetId, Target]:
        return {
            target_id: Target(
                target_id,
                target_config,
            )
            for target_id, target_config in self._config.cma_system.targets.items()
        }

    @property
    def all_targets(self) -> dict[TargetId, Target]:
        return {
            target_id: Target(
                target_id,
                target_config,
            )
            for target_id, target_config in self._config.all_targets.items()
        }

    def add_target(self, target: Target) -> None:
        self._config.site.targets[target.ident] = target.config
        self._config.save()

    def delete_target(self, target_id: TargetId) -> None:
        del self._config.site.targets[target_id]
        self._config.save()

    def add_job(self, job: "Job") -> None:
        self._config.site.jobs[job.ident] = job.config
        self._config.save()
        self._save_cronjobs()

    def delete_job(self, job_id: str) -> None:
        del self._config.site.jobs[job_id]
        self._config.save()
        self._save_cronjobs()

    def _save_cronjobs(self) -> None:
        with Path(self._cronjob_path).open("w", encoding="utf-8") as f:
            self._write_cronjob_header(f)
            for job in self.jobs.values():
                cron_config = job.cron_config()
                if cron_config:
                    f.write("%s\n" % "\n".join(cron_config))

        self._apply_cron_config()

    def _write_cronjob_header(self, f: TextIOWrapper) -> None:
        f.write("# Written by mkbackup configuration\n")

    def _apply_cron_config(self):
        completed_process = subprocess.run(
            ["omd", "restart", "crontab"],
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if completed_process.returncode:
            raise MKGeneralException(
                _("Failed to apply the cronjob config: %s") % completed_process.stdout
            )


# .
#   .--Jobs----------------------------------------------------------------.
#   |                            _       _                                 |
#   |                           | | ___ | |__  ___                         |
#   |                        _  | |/ _ \| '_ \/ __|                        |
#   |                       | |_| | (_) | |_) \__ \                        |
#   |                        \___/ \___/|_.__/|___/                        |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Backup job handling. A backup job is the entity to describe a single |
#   | backup process which has it's own state, can be executed manually    |
#   | and also scheduled to be executed in a predefined interval.          |
#   '----------------------------------------------------------------------'


class StateConfig(TypedDict, total=False):
    state: str | None
    started: None
    output: str
    pid: int
    success: bool


# Abstract class for backup jobs (Job) and restore job (RestoreJob)
class MKBackupJob(abc.ABC):
    @classmethod
    def state_name(cls, state: str | None) -> str:
        return {
            "started": _("Started"),
            "running": _("Currently running"),
            "finished": _("Ended"),
            None: _("Never executed"),
        }[state]

    @abc.abstractmethod
    def state_file_path(self) -> Path:
        ...

    def cleanup(self) -> None:
        try:
            self.state_file_path().unlink()
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    def state(self) -> StateConfig:
        try:
            with self.state_file_path().open(encoding="utf-8") as f:
                state = json.load(f)
        except OSError as e:
            if e.errno == errno.ENOENT:  # not existant
                state = {
                    "state": None,
                    "started": None,
                    "output": "",
                }
            else:
                raise
        except Exception as e:
            raise MKGeneralException(
                _('Failed to parse state file "%s": %s') % (self.state_file_path(), e)
            )

        # Fix data structure when the process has been killed
        if state["state"] == "running" and not os.path.exists("/proc/%d" % state["pid"]):
            state.update(
                {
                    "state": "finished",
                    "finished": max(state["started"], self.state_file_path().stat().st_mtime),
                    "success": False,
                }
            )

        return state

    def was_started(self) -> bool:
        return self.state_file_path().exists()

    def is_running(self) -> bool:
        if not self.was_started():
            return False

        state = self.state()
        return state["state"] in ["started", "running"] and os.path.exists(
            "/proc/%d" % state["pid"]
        )

    def start(self, env: Mapping[str, str] | None = None) -> None:
        completed_process = subprocess.run(
            self._start_command(),
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            encoding="utf-8",
            env=env,
            check=False,
        )
        if completed_process.returncode != 0:
            raise MKGeneralException(_("Failed to start the job: %s") % completed_process.stdout)

    @abc.abstractmethod
    def _start_command(self) -> Sequence[str | Path]:
        ...

    def stop(self) -> None:
        state = self.state()
        pgid = os.getpgid(state["pid"])

        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError as e:
            if e.errno == errno.ESRCH:
                pass
            else:
                raise

        wait = 5.0  # sec
        while os.path.exists("/proc/%d" % state["pid"]) and wait > 0:
            time.sleep(0.5)
            wait -= 0.5

        # When still running after 5 seconds, enforce
        if wait == 0:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError as e:
                if e.errno == errno.ESRCH:
                    pass
                else:
                    raise


class Job(MKBackupJob):
    def __init__(self, ident: str, config: JobConfig) -> None:
        self.ident: Final = ident
        self.config: Final = config

    @property
    def title(self) -> str:
        return self.config["title"]

    def target_ident(self) -> TargetId:
        return self.config["target"]

    def key_ident(self) -> str | None:
        return self.config["encrypt"]

    def is_encrypted(self) -> bool:
        return self.config["encrypt"] is not None

    def state_file_path(self) -> Path:
        return omd_root / "var/check_mk/backup" / ("%s.state" % self.ident)

    def _start_command(self) -> Sequence[str | Path]:
        return [mkbackup_path(), "backup", "--background", self.ident]

    def schedule(self) -> ScheduleConfig | None:
        return self.config["schedule"]

    def cron_config(self) -> list[str]:
        if not (schedule := self.config["schedule"]) or schedule["disabled"]:
            return []
        userspec = self._cron_userspec()
        cmdline = self._cron_cmdline()
        return [f"{timespec} {userspec}{cmdline}" for timespec in self._cron_timespecs(schedule)]

    @staticmethod
    def _cron_timespecs(schedule: ScheduleConfig) -> Sequence[str]:
        period = schedule["period"]
        times = schedule["timeofday"]

        if period == "day":
            dayspec = "* * *"

        elif period[0] == "week":
            # 0-6
            dayspec = "* * %d" % (period[1] + 1,)

        elif period[0] == "month_begin":
            # 1-28
            dayspec = "%d * *" % period[1]

        else:
            assert_never()

        # times: list of two element tuples (hours, minutes)
        timespecs = []
        for hour, minute in times:
            timespecs.append("%d %d %s" % (minute, hour, dayspec))

        return timespecs

    def _cron_userspec(self) -> str:
        if os.environ.get("OMD_SITE"):
            return ""
        return "root "

    def _cron_cmdline(self) -> str:
        return "mkbackup backup %s >/dev/null" % self.ident


class PageBackup:
    def title(self) -> str:
        return _("Site backup")

    def __init__(self, key_store: key_mgmt.KeypairStore) -> None:
        super().__init__()
        self.key_store = key_store

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        menu = PageMenu(
            dropdowns=[
                PageMenuDropdown(
                    name="backups",
                    title=_("Backups"),
                    topics=[
                        PageMenuTopic(
                            title=_("Setup"),
                            entries=list(self._page_menu_entries_setup()),
                        ),
                        PageMenuTopic(
                            title=_("Restore from backup"),
                            entries=[
                                PageMenuEntry(
                                    title=_("Restore"),
                                    icon_name={
                                        "icon": "backup",
                                        "emblem": "refresh",
                                    },
                                    item=make_simple_link(
                                        makeuri_contextless(request, [("mode", "backup_restore")])
                                    ),
                                    is_shortcut=True,
                                    is_suggested=True,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            breadcrumb=breadcrumb,
        )
        menu.add_doc_reference(_("Backups"), DocReference.BACKUPS)
        return menu

    def _page_menu_entries_setup(self) -> Iterator[PageMenuEntry]:
        yield PageMenuEntry(
            title=_("Backup targets"),
            icon_name="backup_targets",
            item=make_simple_link(makeuri_contextless(request, [("mode", "backup_targets")])),
            is_shortcut=True,
            is_suggested=True,
        )
        yield PageMenuEntry(
            title=_("Backup encryption keys"),
            icon_name="signature_key",
            item=make_simple_link(makeuri_contextless(request, [("mode", "backup_keys")])),
            is_shortcut=True,
            is_suggested=True,
        )
        yield PageMenuEntry(
            title=_("Add job"),
            icon_name="new",
            item=make_simple_link(makeuri_contextless(request, [("mode", "edit_backup_job")])),
            is_shortcut=True,
            is_suggested=True,
        )

    def action(self) -> ActionResult:
        if (ident := request.var("_job")) is None:
            raise MKUserError("_job", _("Missing job ID."))

        try:
            job = Config.load().jobs[ident]
        except KeyError:
            raise MKUserError("_job", _("This backup job does not exist."))

        action = request.var("_action")

        if not transactions.check_transaction():
            return HTTPRedirect(makeuri_contextless(request, [("mode", "backup")]))

        if action == "delete":
            self._delete_job(job)

        elif action == "start":
            self._start_job(job)

        elif action == "stop":
            self._stop_job(job)

        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup")]))

    def _delete_job(self, job: Job) -> None:
        if job.is_running():
            raise MKUserError("_job", _("This job is currently running."))

        job.cleanup()

        with contextlib.suppress(KeyError):
            Config.load().delete_job(job.ident)

        flash(_("The job has been deleted."))

    def _start_job(self, job: Job) -> None:
        job.start()
        flash(_("The backup has been started."))

    def _stop_job(self, job: Job) -> None:
        job.stop()
        flash(_("The backup has been stopped."))

    def page(self) -> None:
        show_key_download_warning(self.key_store.load())
        self._show_job_list()

    def _show_job_list(self) -> None:  # pylint: disable=too-many-branches
        html.h3(_("Jobs"))
        with table_element(sortable=False, searchable=False) as table:

            for job in sorted(Config.load().jobs.values(), key=lambda j: j.ident):
                table.row()
                table.cell(_("Actions"), css=["buttons"])
                delete_url = make_confirm_link(
                    url=makeactionuri_contextless(
                        request,
                        transactions,
                        [("mode", "backup"), ("_action", "delete"), ("_job", job.ident)],
                    ),
                    message=_("Do you really want to delete this job?"),
                )
                edit_url = makeuri_contextless(
                    request,
                    [("mode", "edit_backup_job"), ("job", job.ident)],
                )
                state_url = makeuri_contextless(
                    request,
                    [("mode", "backup_job_state"), ("job", job.ident)],
                )

                state = job.state()

                if not job.is_running():
                    html.icon_button(edit_url, _("Edit this backup job"), "edit")
                    html.icon_button(delete_url, _("Delete this backup job"), "delete")

                if state["state"] is not None:
                    html.icon_button(
                        state_url, _("Show current / last state of this backup job"), "backup_state"
                    )

                if not job.is_running():
                    start_url = makeactionuri_contextless(
                        request,
                        transactions,
                        [
                            ("mode", "backup"),
                            ("_action", "start"),
                            ("_job", job.ident),
                        ],
                    )

                    html.icon_button(start_url, _("Manually start this backup"), "backup_start")
                else:
                    stop_url = makeactionuri_contextless(
                        request,
                        transactions,
                        [
                            ("mode", "backup"),
                            ("_action", "stop"),
                            ("_job", job.ident),
                        ],
                    )

                    html.icon_button(stop_url, _("Stop this backup job"), "backup_stop")

                table.cell(_("Name"), job.title)

                css = "state0"
                state_txt = job.state_name(state["state"])
                if state["state"] == "finished":
                    if not state["success"]:
                        css = "state2"
                        state_txt = _("Failed")
                    else:
                        state_txt = _("Finished")
                elif state["state"] is None:
                    css = ""

                table.cell(_("State"), css=[css])
                html.write_html(HTMLWriter.render_span(state_txt))

                table.cell(_("Runtime"))
                if state["started"]:
                    html.write_text(_("Started at %s") % render.date_and_time(state["started"]))
                    duration = time.time() - state["started"]
                    if state["state"] == "finished":
                        html.write_text(
                            ", Finished at %s" % render.date_and_time(state["finished"])
                        )
                        duration = state["finished"] - state["started"]

                    if "size" in state:
                        size_txt = "Size: %s, " % render.fmt_bytes(state["size"])
                    else:
                        size_txt = ""

                    html.write_text(
                        _(" (Duration: %s, %sIO: %s/s)")
                        % (
                            render.timespan(duration),
                            size_txt,
                            render.fmt_bytes(state["bytes_per_second"]),
                        )
                    )

                table.cell(_("Next run"))
                schedule = job.schedule()
                if not schedule:
                    html.write_text(_("Only execute manually"))

                elif schedule["disabled"]:
                    html.write_text(_("Disabled"))

                elif schedule["timeofday"]:
                    # find the next time of all configured times
                    times = []
                    for timespec in schedule["timeofday"]:
                        times.append(next_scheduled_time(schedule["period"], timespec))

                    html.write_text(time.strftime("%Y-%m-%d %H:%M", time.localtime(min(times))))


class PageEditBackupJob:
    def __init__(self, key_store: key_mgmt.KeypairStore) -> None:
        super().__init__()
        self.key_store = key_store
        job_ident = request.get_str_input("job")

        if job_ident is not None:
            try:
                job = Config.load().jobs[job_ident]
            except KeyError:
                raise MKUserError("target", _("This backup job does not exist."))

            if job.is_running():
                raise MKUserError("_job", _("This job is currently running."))

            self._new = False
            self._ident: str | None = job_ident
            self._job_cfg: JobConfig | dict[str, object] = job.config
            self._title = _("Edit backup job: %s") % job.title
        else:
            self._new = True
            self._ident = None
            self._job_cfg = {}
            self._title = _("New backup job")

    def title(self) -> str:
        return self._title

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        return make_simple_form_page_menu(
            _("Job"), breadcrumb, form_name="edit_job", button_name="_save"
        )

    def vs_backup_schedule(self) -> Alternative:
        return Alternative(
            title=_("Schedule"),
            elements=[
                FixedValue(
                    value=None,
                    title=_("Execute manually"),
                    totext=_("Only execute manually"),
                ),
                Dictionary(
                    title=_("Schedule execution"),
                    elements=[
                        (
                            "disabled",
                            Checkbox(
                                title=_("Disable"),
                                label=_("Currently disable scheduled execution of this job"),
                            ),
                        ),
                        ("period", SchedulePeriod(from_end=False)),
                        (
                            "timeofday",
                            ListOf(
                                valuespec=Timeofday(
                                    default_value=(0, 0),
                                    allow_empty=False,
                                ),
                                title=_("Time of day to start the backup at"),
                                movable=False,
                                default_value=[(0, 0)],
                                add_label=_("Add new time"),
                                empty_text=_("Please specify at least one time."),
                                allow_empty=False,
                            ),
                        ),
                    ],
                    optional_keys=[],
                ),
            ],
        )

    def vs_backup_job(self, config: Config) -> Dictionary:
        if self._new:
            ident_attr = [
                (
                    "ident",
                    ID(
                        title=_("Unique ID"),
                        help=_(
                            "The ID of the job must be a unique text. It will be used as an internal key "
                            "when objects refer to the job."
                        ),
                        allow_empty=False,
                        size=12,
                        validate=lambda ident, varprefix: self._validate_backup_job_ident(
                            config,
                            ident,
                            varprefix,
                        ),
                    ),
                )
            ]
        else:
            ident_attr = [
                (
                    "ident",
                    FixedValue(value=self._ident, title=_("Unique ID")),
                )
            ]

        return Dictionary(
            title=_("Backup job"),
            elements=ident_attr
            + [
                (
                    "title",
                    TextInput(
                        title=_("Title"),
                        allow_empty=False,
                        size=64,
                    ),
                ),
                (
                    "target",
                    DropdownChoice(
                        title=_("Target"),
                        # TODO: understand why mypy complains
                        choices=self.backup_target_choices(config),  # type: ignore[misc]
                        validate=lambda target_id, varprefix: self._validate_target(
                            config,
                            target_id,
                            varprefix,
                        ),
                        invalid_choice="complain",
                    ),
                ),
                ("schedule", self.vs_backup_schedule()),
                (
                    "compress",
                    Checkbox(
                        title=_("Compression"),
                        help=_(
                            "Enable gzip compression of the backed up files. The tar archives "
                            "created by the backup are gzipped during backup."
                        ),
                        label=_("Compress the backed up files"),
                    ),
                ),
                (
                    "encrypt",
                    Alternative(
                        title=_("Encryption"),
                        help=_(
                            "Enable encryption of the backed up files. The tar archives "
                            "created by the backup are encrypted using the specified key "
                            "during backup. You will need the private key and the "
                            "passphrase to decrypt the backup."
                        ),
                        elements=[
                            FixedValue(
                                value=None,
                                title=_("Do not encrypt the backup"),
                                totext="",
                            ),
                            DropdownChoice(
                                title=_("Encrypt the backup using the key:"),
                                choices=self.backup_key_choices,
                                invalid_choice="complain",
                            ),
                        ],
                    ),
                ),
                (
                    "no_history",
                    Checkbox(
                        title=_("Do not backup historical data"),
                        help=_(
                            "You may use this option to create a much smaller partial backup of the site."
                        ),
                        label=_(
                            "Do not backup metric data (RRD files), the monitoring history and log files"
                        ),
                    ),
                ),
            ],
            optional_keys=[],
            render="form",
        )

    def _validate_target(
        self,
        config: Config,
        target_id: TargetId | None,
        varprefix: str,
    ) -> None:
        if not target_id:
            raise MKUserError(varprefix, _("You need to provide an ID"))
        config.all_targets[target_id].validate(varprefix)

    def _validate_backup_job_ident(self, config: Config, value: str, varprefix: str) -> None:
        if value == "restore":
            raise MKUserError(varprefix, _("You need to choose another ID."))

        if value in config.jobs:
            raise MKUserError(varprefix, _("This ID is already used by another backup job."))

    def backup_key_choices(self) -> Sequence[tuple[str, str]]:
        return self.key_store.choices()

    def backup_target_choices(self, config: Config) -> Sequence[tuple[TargetId, str]]:
        return [
            (
                target.ident,
                target.title,
            )
            for target in sorted(
                config.all_targets.values(),
                key=lambda t: t.ident,
            )
        ]

    def action(self) -> ActionResult:
        if not transactions.check_transaction():
            return HTTPRedirect(makeuri_contextless(request, [("mode", "backup")]))

        backup_config = Config.load()
        vs = self.vs_backup_job(backup_config)

        job_config = vs.from_html_vars("edit_job")
        vs.validate_value(job_config, "edit_job")

        if "ident" in job_config:
            self._ident = job_config.pop("ident")
        self._job_cfg = cast(JobConfig, job_config)
        if self._ident is None:
            raise MKGeneralException("Cannot create or modify job without identifier")

        backup_config.add_job(
            Job(
                self._ident,
                self._job_cfg,
            )
        )

        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup")]))

    def page(self) -> None:
        html.begin_form("edit_job", method="POST")
        html.prevent_password_auto_completion()

        vs = self.vs_backup_job(Config.load())

        vs.render_input("edit_job", dict(self._job_cfg))
        vs.set_focus("edit_job")
        forms.end()

        html.hidden_fields()
        html.end_form()


_TBackupJob = TypeVar("_TBackupJob", bound=MKBackupJob)


class PageAbstractMKBackupJobState(abc.ABC, Generic[_TBackupJob]):
    @property
    @abc.abstractmethod
    def ident(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def job(self) -> _TBackupJob:
        ...

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        return PageMenu(dropdowns=[], breadcrumb=breadcrumb)

    def page(self) -> None:
        html.open_div(id_="job_details")
        self.show_job_details()
        html.close_div()
        html.javascript(
            "cmk.backup.refresh_job_details('%s', '%s', %s)"
            % (self._update_url(), self.ident, "true")
        )

    def _update_url(self) -> str:
        return "ajax_backup_job_state.py?job=%s" % self.ident

    def show_job_details(self) -> None:
        state = self.job.state()

        html.open_table(class_=["data", "backup_job"])

        if state["state"] is None:
            css = []
            state_txt = self.job.state_name(state["state"])
        elif state["state"] != "finished":
            css = ["state0"]
            state_txt = self.job.state_name(state["state"])
        elif state["success"]:
            css = ["state0"]
            state_txt = _("Finished")
        else:
            css = ["state2"]
            state_txt = _("Failed")

        html.open_tr(class_=["data", "even0"])
        html.td(_("State"), class_=["left", "legend"])
        html.td(state_txt, class_=["state"] + css)
        html.close_tr()

        html.open_tr(class_=["data", "odd0"])
        html.td(_("Runtime"), class_="left")
        html.open_td()
        if state["started"]:
            html.write_text(_("Started at %s") % render.date_and_time(state["started"]))
            duration = time.time() - state["started"]
            if state["state"] == "finished":
                html.write_text(", Finished at %s" % render.date_and_time(state["started"]))
                duration = state["finished"] - state["started"]

            html.write_text(_(" (Duration: %s)") % render.timespan(duration))
        html.close_td()
        html.close_tr()

        html.open_tr(class_=["data", "even0"])
        html.td(_("Output"), class_=["left", "legend"])
        html.open_td()
        html.open_div(class_="log_output", style="height: 400px;", id_="progress_log")
        html.pre(state["output"])
        html.close_div()
        html.close_td()
        html.close_tr()

        html.close_table()


class PageBackupJobState(PageAbstractMKBackupJobState[Job]):
    def __init__(self) -> None:
        super().__init__()
        self._from_vars()

    @property
    def ident(self) -> str:
        return self._ident

    @property
    def job(self) -> Job:
        return self._job

    def title(self) -> str:
        return _("Job state: %s") % self.job.title

    def _from_vars(self) -> None:
        if (job_ident := request.var("job")) is None:
            raise MKUserError("job", _("You need to specify a backup job."))
        try:
            tmp = Config.load().jobs[job_ident]
        except KeyError:
            raise MKUserError("job", _("This backup job does not exist."))
        self._job = tmp
        self._ident = job_ident


# .
#   .--Target Types--------------------------------------------------------.
#   |      _____                    _     _____                            |
#   |     |_   _|_ _ _ __ __ _  ___| |_  |_   _|   _ _ __   ___  ___       |
#   |       | |/ _` | '__/ _` |/ _ \ __|   | || | | | '_ \ / _ \/ __|      |
#   |       | | (_| | | | (_| |  __/ |_    | || |_| | |_) |  __/\__ \      |
#   |       |_|\__,_|_|  \__, |\___|\__|   |_| \__, | .__/ \___||___/      |
#   |                    |___/                 |___/|_|                    |
#   +----------------------------------------------------------------------+
#   | A target type implements the handling of different protocols to use  |
#   | for storing the backup.                                              |
#   '----------------------------------------------------------------------'


class ABCBackupTargetType(abc.ABC):
    @abc.abstractmethod
    def __init__(self, params: Mapping[str, object]) -> None:
        ...

    @property
    @abc.abstractmethod
    def parameters(self) -> Mapping[str, object]:
        ...

    @staticmethod
    @abc.abstractmethod
    def ident() -> str:
        ...

    @staticmethod
    @abc.abstractmethod
    def title() -> str:
        ...

    @classmethod
    @abc.abstractmethod
    def valuespec(cls) -> Dictionary:
        ...

    @abc.abstractmethod
    def validate(self, varprefix: str) -> None:
        ...

    @abc.abstractmethod
    def backups(self) -> Mapping[str, RawBackupInfo]:
        ...

    @abc.abstractmethod
    def remove_backup(self, backup_ident: str) -> None:
        ...

    def render(self) -> ValueSpecText:
        return self.valuespec().value_to_html(dict(self.parameters))


class TargetTypeRegistry(Registry[type[ABCBackupTargetType]]):
    def plugin_name(self, instance: type[ABCBackupTargetType]) -> str:
        return instance.ident()


target_type_registry = TargetTypeRegistry()


@target_type_registry.register
class BackupTargetLocal(ABCBackupTargetType):
    def __init__(self, params: LocalTargetParams) -> None:
        self._params = params

    @property
    def parameters(self) -> LocalTargetParams:
        return self._params

    @staticmethod
    def ident() -> str:
        return "local"

    @staticmethod
    def title() -> str:
        return _("Local path")

    @classmethod
    def valuespec(cls) -> Dictionary:
        return Dictionary(
            elements=[
                (
                    "path",
                    AbsoluteDirname(
                        title=_("Directory to save the backup to"),
                        help=_(
                            "This can be a local directory of your choice. You can also use this "
                            "option if you want to save your backup to a network share using "
                            "NFS, Samba or similar. But you will have to care about mounting the "
                            "network share on your own."
                        ),
                        allow_empty=False,
                        size=64,
                    ),
                ),
                (
                    "is_mountpoint",
                    Checkbox(
                        title=_("Mountpoint"),
                        label=_("Is mountpoint"),
                        help=_(
                            "When this is checked, the backup ensures that the configured path "
                            "is a mountpoint. If there is no active mount on the path, the backup "
                            "fails with an error message."
                        ),
                        default_value=True,
                    ),
                ),
            ],
            optional_keys=[],
            validate=lambda params, varprefix: cls(cast(LocalTargetParams, params)).validate(
                varprefix
            ),
        )

    def validate(self, varprefix: str) -> None:
        self._validate_path(self.parameters["path"], varprefix)

    @staticmethod
    def _validate_path(path: str, varprefix: str) -> None:
        if not is_canonical(path):
            raise MKUserError(varprefix, _("You have to provide a canonical path."))

        if cmk_version.is_cma() and not path.startswith("/mnt/"):
            raise MKUserError(
                varprefix,
                _(
                    "You can only use mountpoints below the <tt>/mnt</tt> "
                    "directory as backup targets."
                ),
            )

        if not os.path.isdir(path):
            raise MKUserError(
                varprefix,
                _(
                    "The path does not exist or is not a directory. You "
                    "need to specify an already existing directory."
                ),
            )

        # Check write access for the site user
        try:
            test_file_path = os.path.join(path, "write_test_%d" % time.time())
            with open(test_file_path, "wb"):
                pass
            os.unlink(test_file_path)
        except OSError:
            if cmk_version.is_cma():
                raise MKUserError(
                    varprefix,
                    _(
                        "Failed to write to the configured directory. The target directory needs "
                        "to be writable."
                    ),
                )
            raise MKUserError(
                varprefix,
                _(
                    "Failed to write to the configured directory. The site user needs to be able to "
                    "write the target directory. The recommended way is to make it writable by the "
                    'group "omd".'
                ),
            )

    # TODO: Duplicate code with mkbackup
    def backups(self) -> Mapping[str, RawBackupInfo]:
        backups = {}

        self.verify_target_is_ready()

        for path in glob.glob("%s/*/mkbackup.info" % self.parameters["path"]):
            try:
                info = self._load_backup_info(path)
            except OSError as e:
                if e.errno == errno.EACCES:
                    continue  # Silently skip not permitted files
                raise

            backups[info["backup_id"]] = info

        return backups

    # TODO: Duplocate code with mkbackup
    def verify_target_is_ready(self) -> None:
        if self.parameters["is_mountpoint"] and not os.path.ismount(self.parameters["path"]):
            raise MKGeneralException(
                "The backup target path is configured to be a mountpoint, "
                "but nothing is mounted."
            )

    # TODO: Duplicate code with mkbackup
    def _load_backup_info(self, path: str) -> RawBackupInfo:
        with Path(path).open(encoding="utf-8") as f:
            info = json.load(f)

        # Load the backup_id from the second right path component. This is the
        # base directory of the mkbackup.info file. The user might have moved
        # the directory, e.g. for having multiple backups. Allow that.
        # Maybe we need to changed this later when we allow multiple generations
        # of backups.
        info["backup_id"] = os.path.basename(os.path.dirname(path))

        return info

    def remove_backup(self, backup_ident: str) -> None:
        self.verify_target_is_ready()
        shutil.rmtree("{}/{}".format(self.parameters["path"], backup_ident))


# .
#   .--Targets-------------------------------------------------------------.
#   |                  _____                    _                          |
#   |                 |_   _|_ _ _ __ __ _  ___| |_ ___                    |
#   |                   | |/ _` | '__/ _` |/ _ \ __/ __|                   |
#   |                   | | (_| | | | (_| |  __/ |_\__ \                   |
#   |                   |_|\__,_|_|  \__, |\___|\__|___/                   |
#   |                                |___/                                 |
#   +----------------------------------------------------------------------+
#   | Specifying backup targets, the user tells the backup system which    |
#   | destinations can be used for the backups. Each destination has it's  |
#   | own protocol and specific parameters to specify how to backup.       |
#   '----------------------------------------------------------------------'


class Target:
    def __init__(self, ident: TargetId, config: TargetConfig) -> None:
        self.ident: Final = ident
        self.config: Final = config

    @property
    def title(self) -> str:
        return self.config["title"]

    def _target_type(self) -> ABCBackupTargetType:
        target_type_ident, target_params = self.config["remote"]
        try:
            target_type = target_type_registry[target_type_ident]
        except KeyError:
            raise MKUserError(
                None,
                _("Unknown target type: %s. Available types: %s.")
                % (
                    target_type_ident,
                    ", ".join(target_type_registry),
                ),
            )
        return target_type(target_params)

    def show_backup_list(self, only_type: str) -> None:
        with table_element(sortable=False, searchable=False) as table:

            for backup_ident, info in sorted(self.backups().items()):
                if info["type"] != only_type:
                    continue

                table.row()
                table.cell(_("Actions"), css=["buttons"])

                delete_url = make_confirm_link(
                    url=makeactionuri(
                        request, transactions, [("_action", "delete"), ("_backup", backup_ident)]
                    ),
                    message=_("Do you really want to delete this backup?"),
                )

                html.icon_button(delete_url, _("Delete this backup"), "delete")

                start_url = make_confirm_link(
                    url=makeactionuri(
                        request, transactions, [("_action", "start"), ("_backup", backup_ident)]
                    ),
                    message=_("Do you really want to start the restore of this backup?"),
                )

                html.icon_button(
                    start_url,
                    _("Start restore of this backup"),
                    {
                        "icon": "backup",
                        "emblem": "refresh",
                    },
                )

                from_info = info["hostname"]
                if "site_id" in info:
                    from_info += " (Site: {}, Version: {})".format(
                        info["site_id"],
                        info["site_version"],
                    )
                else:
                    from_info += " (Version: %s)" % info["cma_version"]

                table.cell(_("Backup-ID"), backup_ident)
                table.cell(_("From"), from_info)
                table.cell(_("Finished"), render.date_and_time(info["finished"]))
                table.cell(_("Size"), render.fmt_bytes(info["size"]))
                table.cell(_("Encrypted"))
                if info["config"]["encrypt"] is not None:
                    html.write_text(info["config"]["encrypt"])
                else:
                    html.write_text(_("No"))

                if info["type"] == "Appliance":
                    table.cell(_("Clustered"))
                    if "cma_cluster" not in info:
                        html.write_text(_("Standalone"))
                    else:
                        html.write_text(_("Clustered"))
                        if not info["cma_cluster"]["is_inactive"]:
                            html.write_text(" (%s)" % _("Active node"))
                        else:
                            html.write_text(" (%s)" % _("Standby node"))

    def backups(self) -> Mapping[str, RawBackupInfo]:
        return self._target_type().backups()

    def remove_backup(self, backup_ident: str) -> None:
        self._target_type().remove_backup(backup_ident)

    def validate(self, varprefix: str) -> None:
        self._target_type().validate(varprefix)

    def render(self) -> ValueSpecText:
        return self._target_type().render()


def _show_site_and_system_targets(config: Config) -> None:
    _show_target_list(config.site_targets.values(), False)
    if cmk_version.is_cma():
        _show_target_list(config.cma_system_targets.values(), True)


def _show_target_list(targets: Iterable[Target], targets_are_cma: bool) -> None:
    html.h2(_("System global targets") if targets_are_cma else _("Targets"))
    if targets_are_cma:
        html.p(
            _(
                "These backup targets can not be edited here. You need to "
                "open the device backup management."
            )
        )

    with table_element(sortable=False, searchable=False) as table:

        for target in sorted(targets, key=lambda t: t.ident):
            table.row()
            table.cell(_("Actions"), css=["buttons"])
            restore_url = makeuri_contextless(
                request,
                [("mode", "backup_restore"), ("target", target.ident)],
            )
            html.icon_button(
                restore_url,
                _("Restore from this backup target"),
                {
                    "icon": "backup",
                    "emblem": "refresh",
                },
            )

            if not targets_are_cma:
                delete_url = make_confirm_link(
                    url=makeactionuri_contextless(
                        request,
                        transactions,
                        [("mode", "backup_targets"), ("target", target.ident)],
                    ),
                    message=_("Do you really want to delete this target?"),
                )
                edit_url = makeuri_contextless(
                    request,
                    [("mode", "edit_backup_target"), ("target", target.ident)],
                )

                html.icon_button(edit_url, _("Edit this backup target"), "edit")
                html.icon_button(delete_url, _("Delete this backup target"), "delete")

                table.cell(_("Title"), target.title)
                table.cell(_("Destination"), target.render())


class PageBackupTargets:
    def title(self) -> str:
        return _("Site backup targets")

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        return PageMenu(
            dropdowns=[
                PageMenuDropdown(
                    name="targets",
                    title=_("Targets"),
                    topics=[
                        PageMenuTopic(
                            title=_("Add target"),
                            entries=[
                                PageMenuEntry(
                                    title=_("Add target"),
                                    icon_name="new",
                                    item=make_simple_link(
                                        makeuri_contextless(
                                            request,
                                            [("mode", "edit_backup_target")],
                                        )
                                    ),
                                    is_shortcut=True,
                                    is_suggested=True,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            breadcrumb=breadcrumb,
        )

    def action(self) -> ActionResult:
        if not transactions.check_transaction():
            return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_targets")]))

        if not (ident := request.var("target")):
            raise MKUserError("target", _("This backup target does not exist."))

        config = Config.load()

        try:
            target = config.site_targets[TargetId(ident)]
        except KeyError:
            raise MKUserError("target", _("This backup target does not exist."))

        self._verify_not_used(config, target.ident)

        with contextlib.suppress(KeyError):
            config.delete_target(target.ident)

        flash(_("The target has been deleted."))
        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_targets")]))

    def _verify_not_used(self, config: Config, target_id: TargetId) -> None:
        if jobs := [job for job in config.jobs.values() if job.target_ident() == target_id]:
            raise MKUserError(
                "target",
                _("You can not delete this target because it is used by these backup jobs: %s")
                % ", ".join(job.title for job in jobs),
            )

    def page(self) -> None:
        _show_site_and_system_targets(Config.load())


class PageEditBackupTarget:
    def __init__(self) -> None:
        super().__init__()
        target_ident = request.var("target")

        if target_ident is not None:
            target_ident = TargetId(target_ident)
            try:
                target = Config.load().site_targets[target_ident]
            except KeyError:
                raise MKUserError("target", _("This backup target does not exist."))

            self._new = False
            self._ident: TargetId | None = target_ident
            self._target_cfg: TargetConfig | dict[str, object] = target.config
            self._title = _("Edit backup target: %s") % target.title
        else:
            self._new = True
            self._ident = None
            self._target_cfg = {}
            self._title = _("New backup target")

    def title(self) -> str:
        return self._title

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        return make_simple_form_page_menu(
            _("Target"), breadcrumb, form_name="edit_target", button_name="_save"
        )

    def vs_backup_target(self, config: Config) -> Dictionary:
        if self._new:
            ident_attr = [
                (
                    "ident",
                    ID(
                        title=_("Unique ID"),
                        help=_(
                            "The ID of the target must be a unique text. It will be used as an internal key "
                            "when objects refer to the target."
                        ),
                        allow_empty=False,
                        size=12,
                        validate=lambda ident, varprefix: self.validate_backup_target_ident(
                            config,
                            ident,
                            varprefix,
                        ),
                    ),
                ),
            ]
        else:
            ident_attr = [
                (
                    "ident",
                    FixedValue(
                        value=self._ident,
                        title=_("Unique ID"),
                    ),
                ),
            ]

        return Dictionary(
            title=_("Backup target"),
            elements=ident_attr
            + [
                (
                    "title",
                    TextInput(
                        title=_("Title"),
                        allow_empty=False,
                        size=64,
                    ),
                ),
                (
                    "remote",
                    CascadingDropdown(
                        title=_("Destination"),
                        choices=[
                            (
                                target_type.ident(),
                                target_type.title(),
                                target_type.valuespec(),
                            )
                            for target_type in target_type_registry.values()
                        ],
                    ),
                ),
            ],
            optional_keys=[],
            render="form",
        )

    def validate_backup_target_ident(self, config: Config, value: str, varprefix: str) -> None:
        if TargetId(value) in config.site_targets:
            raise MKUserError(varprefix, _("This ID is already used by another backup target."))

    def action(self) -> ActionResult:
        if not transactions.check_transaction():
            return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_targets")]))

        backup_config = Config.load()
        vs = self.vs_backup_target(backup_config)

        target_config = vs.from_html_vars("edit_target")
        vs.validate_value(target_config, "edit_target")

        if "ident" in target_config:
            self._ident = TargetId(target_config.pop("ident"))
        self._target_cfg = cast(TargetConfig, target_config)

        if self._ident is None:
            raise MKGeneralException("Cannot create or modify job without identifier")

        backup_config.add_target(
            Target(
                self._ident,
                self._target_cfg,
            )
        )

        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_targets")]))

    def page(self) -> None:
        html.begin_form("edit_target", method="POST")
        html.prevent_password_auto_completion()

        vs = self.vs_backup_target(Config.load())

        vs.render_input("edit_target", dict(self._target_cfg))
        vs.set_focus("edit_target")
        forms.end()

        html.hidden_fields()
        html.end_form()


# .
#   .--Key Management------------------------------------------------------.
#   |             _  __            __  __                 _                |
#   |            | |/ /___ _   _  |  \/  | __ _ _ __ ___ | |_              |
#   |            | ' // _ \ | | | | |\/| |/ _` | '_ ` _ \| __|             |
#   |            | . \  __/ |_| | | |  | | (_| | | | | | | |_              |
#   |            |_|\_\___|\__, | |_|  |_|\__, |_| |_| |_|\__|             |
#   |                      |___/          |___/                            |
#   +----------------------------------------------------------------------+
#   | Managing of the keys that are used for signing the agents            |
#   '----------------------------------------------------------------------'


class BackupKeypairStore(key_mgmt.KeypairStore):
    pass


class PageBackupKeyManagement(key_mgmt.PageKeyManagement):
    edit_mode = "backup_edit_key"
    upload_mode = "backup_upload_key"
    download_mode = "backup_download_key"

    def title(self) -> str:
        return _("Keys for backups")

    def page(self) -> None:
        show_key_download_warning(self.key_store.load())
        super().page()

    def _key_in_use(self, key_id: int, key: key_mgmt.Key) -> bool:
        for job in Config.load().jobs.values():
            if (job_key_id := job.key_ident()) and str(key_id) == job_key_id:
                return True
        return False

    def _table_title(self) -> str:
        return self.title()

    def _delete_confirm_msg(self) -> str:
        return _(
            "Are you sure you want to delete this key?<br><br>"
            "<b>Beware:</b> Deleting this key "
            "means that you will not be able to encrypt or sign backups with the key. "
            "Already created backups which have been encrypted, can not be decrypted "
            "without access to this key. So please be sure that you either have a "
            "backup or don't need this key anymore."
        )


class PageBackupEditKey(key_mgmt.PageEditKey):
    back_mode = "backup_keys"

    def title(self) -> str:
        return _("Create backup key")

    def _passphrase_help(self) -> str:
        return _(
            "The backup key will be stored encrypted using this passphrase on your "
            "disk. The passphrase will not be stored anywhere. The backup will use "
            "the public key part of the key to sign or encrypt the backups. If you "
            "encrypt a backup, you will need the private key part together with the "
            "passphrase to decrypt the backup."
        )

    def _generate_key(self, alias: str, passphrase: str) -> key_mgmt.Key:
        assert user.id is not None
        key = key_mgmt.generate_key(alias, passphrase, user.id, omd_site())
        # Mark key as not downloaded yet to issue a warning to the user that the key
        # should be backed up. The warning is removed on first download.
        key.not_downloaded = True
        return key


class PageBackupUploadKey(key_mgmt.PageUploadKey):
    back_mode = "backup_keys"

    def title(self) -> str:
        return _("Upload backup key")

    def _passphrase_help(self) -> str:
        return _(
            "The backup key will be stored encrypted using this passphrase on your "
            "disk. The passphrase will not be stored anywhere. The backup will use "
            "the public key part of the key to sign or encrypt the backups. If you "
            "encrypt a backup, you will need the private key part together with the "
            "passphrase to decrypt the backup."
        )


class PageBackupDownloadKey(key_mgmt.PageDownloadKey):
    back_mode = "backup_keys"

    def title(self) -> str:
        return _("Download backup key")

    def _send_download(self, keys: dict[int, key_mgmt.Key], key_id: int) -> None:
        super()._send_download(keys, key_id)
        keys[key_id].not_downloaded = True
        self.key_store.save(keys)

    def _file_name(self, key_id: int, key: Key) -> str:
        return f"Check_MK-{hostname()}-{omd_site()}-backup_key-{key_id}.pem"


def show_key_download_warning(keys: dict[int, key_mgmt.Key]) -> None:
    to_load = [k.alias for k in keys.values() if k.not_downloaded]
    if to_load:
        html.show_warning(
            _(
                "To be able to restore your encrypted backups, you need to "
                "download and keep the backup encryption keys in a safe place. "
                "If you loose your keys or the keys passphrases, your backup "
                "can not be restored.<br>"
                "The following keys have not been downloaded yet: %s"
            )
            % ", ".join(to_load)
        )


# .
#   .--Restore-------------------------------------------------------------.
#   |                  ____           _                                    |
#   |                 |  _ \ ___  ___| |_ ___  _ __ ___                    |
#   |                 | |_) / _ \/ __| __/ _ \| '__/ _ \                   |
#   |                 |  _ <  __/\__ \ || (_) | | |  __/                   |
#   |                 |_| \_\___||___/\__\___/|_|  \___|                   |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Listing backups of targets and controlling the the restore procedure |
#   '----------------------------------------------------------------------'


class RestoreJob(MKBackupJob):
    def __init__(  # type:ignore[no-untyped-def]
        self, target_ident, backup_ident, passphrase=None
    ) -> None:
        super().__init__()
        self._target_ident = target_ident
        self._backup_ident = backup_ident
        self._passphrase = passphrase

    def title(self) -> str:
        return _("Restore")

    def state_file_path(self) -> Path:
        return Path("/tmp/restore-%s.state" % os.environ["OMD_SITE"])

    def complete(self):
        self.cleanup()

    def _start_command(self):
        return [mkbackup_path(), "restore", "--background", self._target_ident, self._backup_ident]

    def start(self, env=None):
        if self._passphrase is not None:
            if env is None:
                env = {}
            env.update(os.environ.copy())
            env["MKBACKUP_PASSPHRASE"] = self._passphrase
        super().start(env)


class PageBackupRestore:
    def __init__(self, key_store: key_mgmt.KeypairStore) -> None:
        super().__init__()
        self.key_store = key_store
        self._load_target()

    def _load_target(self):
        ident = request.var("target")
        if ident is None:
            self._target_ident = None
            self._target = None
            return

        self._target_ident = TargetId(ident)

        try:
            self._target = self._get_target(self._target_ident)
        except KeyError:
            raise MKUserError("target_p_target", _("This backup target does not exist."))

    def _get_target(self, target_ident: TargetId) -> Target:
        return Config.load().all_targets[target_ident]

    def title(self) -> str:
        if not self._target:
            return _("Site restore")
        return _("Restore from target: %s") % self._target.title

    def page_menu(self, breadcrumb: Breadcrumb) -> PageMenu:
        return PageMenu(
            dropdowns=[
                PageMenuDropdown(
                    name="restore",
                    title=_("Restore"),
                    topics=[
                        PageMenuTopic(
                            title=_("Restore job"),
                            entries=[
                                PageMenuEntry(
                                    title=_("Stop"),
                                    icon_name="backup_stop",
                                    item=make_simple_link(
                                        make_confirm_link(
                                            url=makeactionuri(
                                                request, transactions, [("_action", "stop")]
                                            ),
                                            message=_(
                                                "Do you really want to stop the restore of "
                                                "this backup? This will - leave your environment in "
                                                "an undefined state."
                                            ),
                                        )
                                    ),
                                    is_shortcut=True,
                                    is_suggested=True,
                                    is_enabled=self._restore_is_running(),
                                ),
                                PageMenuEntry(
                                    title=_("Complete the restore"),
                                    icon_name="save",
                                    item=make_simple_link(
                                        makeactionuri(
                                            request, transactions, [("_action", "complete")]
                                        )
                                    ),
                                    is_shortcut=True,
                                    is_suggested=True,
                                    is_enabled=self._restore_was_started(),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            breadcrumb=breadcrumb,
        )

    def action(self) -> ActionResult:
        action = request.var("_action")
        backup_ident = request.var("_backup")

        if action is None:
            return None  # Only choosen the target

        if not transactions.check_transaction():
            return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_restore")]))

        if action == "delete":
            self._delete_backup(backup_ident)

        elif action == "complete":
            self._complete_restore(backup_ident)

        elif action == "start":
            return self._start_restore(backup_ident)

        elif action == "stop":
            self._stop_restore(backup_ident)

        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_restore")]))

    def _delete_backup(self, backup_ident) -> None:  # type:ignore[no-untyped-def]
        if self._restore_is_running():
            raise MKUserError(
                None,
                _(
                    "A restore is currently running. You can only delete "
                    "backups while no restore is running."
                ),
            )

        if self._target is None:
            raise Exception("no backup target")
        if backup_ident not in self._target.backups():
            raise MKUserError(None, _("This backup does not exist."))

        self._target.remove_backup(backup_ident)
        flash(_("The backup has been deleted."))

    def _restore_was_started(self):
        return RestoreJob(self._target_ident, None).was_started()

    def _restore_is_running(self):
        return RestoreJob(self._target_ident, None).is_running()

    def _start_restore(self, backup_ident) -> ActionResult:  # type:ignore[no-untyped-def]
        if self._target is None:
            raise Exception("no backup target")
        backup_info = self._target.backups()[backup_ident]
        if backup_info["config"]["encrypt"] is not None:
            return self._start_encrypted_restore(backup_ident, backup_info)
        return self._start_unencrypted_restore(backup_ident)

    def _complete_restore(self, backup_ident) -> None:  # type:ignore[no-untyped-def]
        RestoreJob(self._target_ident, None).complete()

    def _start_encrypted_restore(  # type:ignore[no-untyped-def]
        self, backup_ident, backup_info
    ) -> ActionResult:
        key_digest = backup_info["config"]["encrypt"]

        try:
            _key_id, key = self.key_store.get_key_by_digest(key_digest)
        except KeyError:
            raise MKUserError(
                None,
                _(
                    "The key with the fingerprint %s which is needed to decrypt "
                    "the backup is misssing."
                )
                % key_digest,
            )

        if html.form_submitted("key"):
            try:
                value = self._vs_key().from_html_vars("_key")
                if request.has_var("_key_p_passphrase"):
                    self._vs_key().validate_value(value, "_key")
                    passphrase = value["passphrase"]

                    # Validate the passphrase
                    key_mgmt.decrypt_private_key(key.private_key, passphrase)

                    transactions.check_transaction()  # invalidate transid
                    RestoreJob(self._target_ident, backup_ident, passphrase).start()
                    flash(_("The restore has been started."))
                    return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_restore")]))
            except MKUserError as e:
                user_errors.add(e)

        # Special handling for Checkmk / CMA differences
        title = _("Insert passphrase")
        breadcrumb = make_simple_page_breadcrumb(mega_menu_registry.menu_setup(), title)
        make_header(html, title, breadcrumb, PageMenu(dropdowns=[], breadcrumb=breadcrumb))

        html.show_user_errors()
        html.p(
            _(
                "To be able to decrypt and restore the encrypted backup, you need to enter the "
                "passphrase of the encryption key."
            )
        )
        html.begin_form("key", method="GET")
        html.hidden_field("_action", "start")
        html.hidden_field("_backup", backup_ident)
        html.prevent_password_auto_completion()
        self._vs_key().render_input("_key", {})
        html.button("upload", _("Start restore"))
        self._vs_key().set_focus("_key")
        html.hidden_fields()
        html.end_form()
        html.footer()
        return FinalizeRequest(code=200)

    def _vs_key(self):
        return Dictionary(
            title=_("Properties"),
            elements=[
                (
                    "passphrase",
                    Password(
                        title=_("Passphrase"),
                        allow_empty=False,
                        is_stored_plain=False,
                    ),
                ),
            ],
            optional_keys=False,
            render="form",
        )

    def _start_unencrypted_restore(  # type:ignore[no-untyped-def]
        self, backup_ident
    ) -> ActionResult:
        RestoreJob(self._target_ident, backup_ident).start()
        flash(_("The restore has been started."))
        return HTTPRedirect(makeuri_contextless(request, [("mode", "backup_restore")]))

    def _stop_restore(self, backup_ident) -> None:  # type:ignore[no-untyped-def]
        RestoreJob(self._target_ident, backup_ident).stop()
        flash(_("The restore has been stopped."))

    def page(self) -> None:
        if self._restore_was_started():
            self._show_restore_progress()

        elif self._target:
            self._show_backup_list()

        else:
            self._show_target_list()

    def _show_target_list(self):
        html.p(_("Please choose a target to perform the restore from."))
        _show_site_and_system_targets(Config.load())

    def _show_backup_list(self) -> None:
        assert self._target is not None
        self._target.show_backup_list(only_type="Check_MK")

    def _show_restore_progress(self):
        PageBackupRestoreState().page()


class PageBackupRestoreState(PageAbstractMKBackupJobState[RestoreJob]):
    def __init__(self) -> None:
        super().__init__()
        self._job = RestoreJob(None, None)  # TODO: target_ident and backup_ident needed?
        self._ident = "restore"

    @property
    def ident(self) -> str:
        return self._ident

    @property
    def job(self) -> RestoreJob:
        return self._job
