"""Memory backups and integrity checks."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.config import settings
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.i18n import t
from moha_mind.utils.logging_config import log
from moha_mind.utils.reminder_schedule import DATETIME_FORMAT, RECURRING_REPEATS
from moha_mind.utils.timezone import now_ksa

ONE_OFF_EVENT_TERMS = (
    "meeting",
    "manager",
    "tomorrow",
    "today",
    "tonight",
    "appointment",
    "call",
    "اجتماع",
    "مدير",
    "بكره",
    "بكرا",
    "غدا",
    "غدًا",
    "اليوم",
    "الليلة",
    "موعد",
    "مكالمة",
)


@dataclass
class IntegrityReport:
    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.critical and not self.warnings


class ReliabilityGuardian:
    def __init__(
        self,
        memory: MemoryManager,
        bot: Any | None = None,
        *,
        retention_days: int | None = None,
        max_backups: int | None = None,
    ):
        self.memory = memory
        self.bot = bot
        self.backup_dir = self.memory.memory_path / ".backups"
        self.retention_days = retention_days or int(getattr(settings, "memory_backup_retention_days", 30) or 30)
        self.max_backups = max_backups or int(getattr(settings, "memory_backup_max_count", 60) or 60)

    def scan(self) -> IntegrityReport:
        report = IntegrityReport()
        manifest = self.latest_manifest()
        current = self._memory_file_stats()

        for category, filename in MEMORY_FILES.items():
            stats = current.get(filename)
            if not stats:
                report.critical.append(f"Missing memory file: {filename}")
                continue
            if stats["size"] == 0:
                report.warnings.append(f"Empty memory file: {filename}")

        if manifest:
            previous = manifest.get("memory_files", {})
            self._check_memory_shrinkage(previous, current, report)
        else:
            report.info.append("No previous backup manifest yet; this run will create the first baseline.")

        self._check_summary_cache(report)
        self._check_reminders(report)
        self._check_backup_freshness(report)
        return report

    def create_backup(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = now_ksa().strftime("%Y%m%dT%H%M%S%z")
        final_path = self.backup_dir / f"mohamind-memory-{stamp}.zip"
        temp_path = self.backup_dir / f".{final_path.name}.tmp"

        manifest = self._build_manifest(final_path.name)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in self._iter_backup_files():
                archive.write(path, path.relative_to(self.memory.memory_path).as_posix())
            archive.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        temp_path.replace(final_path)

        manifest_path = self._manifest_path_for_backup(final_path)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._prune_backups()
        log.info(f"Memory backup created: {final_path}")
        return final_path

    async def run(self) -> IntegrityReport:
        log.info("Reliability Guardian: running memory integrity check...")
        repaired = self.repair_malformed_reminder_blocks()
        report = self.scan()
        if repaired:
            report.info.append(f"Repaired malformed reminder blocks: {repaired}")
        backup_path = self.create_backup()
        report.info.append(f"Backup created: {backup_path.name}")

        if self.bot and (getattr(settings, "reliability_send_digest", True) or not report.ok):
            message = self.format_report(report)
            for part in truncate_message(message):
                await self.bot.send_message(part)

        if report.ok:
            log.info("Reliability Guardian: all checks passed")
        else:
            log.warning(
                f"Reliability Guardian: {len(report.critical)} critical issue(s), {len(report.warnings)} warning(s)"
            )
        return report

    def format_report(self, report: IntegrityReport) -> str:
        status = t("guardian.ok") if report.ok else t("guardian.attention")
        lines = [t("guardian.title", status=status)]
        if report.critical:
            lines.append("\n" + t("guardian.critical"))
            lines.extend(f"- {item}" for item in report.critical[:8])
        if report.warnings:
            lines.append("\n" + t("guardian.warnings"))
            lines.extend(f"- {item}" for item in report.warnings[:8])
        if report.info:
            lines.append("\n" + t("guardian.info"))
            lines.extend(f"- {item}" for item in report.info[:6])
        if report.ok:
            lines.append("\n" + t("guardian.footer"))
        return "\n".join(lines)

    def latest_manifest(self) -> dict | None:
        manifests = sorted(self.backup_dir.glob("*.manifest.json"), key=lambda path: path.stat().st_mtime)
        if not manifests:
            return None
        try:
            return json.loads(manifests[-1].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning(f"Could not read backup manifest {manifests[-1]}: {exc}")
            return None

    def repair_malformed_reminder_blocks(self) -> int:
        content = self.memory.read("reminders")
        if not content:
            return 0

        lines = content.splitlines()
        repaired = 0
        out: list[str] = []
        now = now_ksa().replace(tzinfo=None)
        index = 0

        while index < len(lines):
            line = lines[index]
            if not re.match(r"^- \[[ x]\] ", line.strip()):
                out.append(line)
                index += 1
                continue

            block = [line]
            next_index = index + 1
            while next_index < len(lines) and not re.match(r"^- \[[ x]\] ", lines[next_index].strip()):
                block.append(lines[next_index])
                next_index += 1

            parsed_first = self.memory._parse_reminder_line(line)
            if len(block) > 1 and (not parsed_first or not parsed_first.get("remind_at")):
                joined_block = " ".join(part.strip() for part in block if part.strip())
                parsed_block = self.memory._parse_reminder_line(joined_block)
                if parsed_block and parsed_block.get("remind_at"):
                    try:
                        remind_dt = datetime.strptime(parsed_block["remind_at"], DATETIME_FORMAT)
                    except ValueError:
                        pass
                    else:
                        parsed_block["done"] = parsed_block["done"] or remind_dt < now - timedelta(days=2)
                        out.append(self.memory._format_reminder_line(parsed_block))
                        repaired += 1
                        index = next_index
                        continue

            out.extend(block)
            index = next_index

        if repaired:
            self.memory.write(
                "reminders",
                "\n".join(out),
                action="repair_reminders",
                details={"repaired_count": repaired},
            )
        return repaired

    def _manifest_path_for_backup(self, backup_path: Path) -> Path:
        return self.backup_dir / f"{backup_path.stem}.manifest.json"

    def _iter_backup_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.memory.memory_path.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.memory.memory_path)
            if relative.parts and relative.parts[0] == ".backups":
                continue
            files.append(path)
        return sorted(files)

    def _build_manifest(self, backup_name: str) -> dict:
        files = {}
        memory_files = {}
        for path in self._iter_backup_files():
            relative = path.relative_to(self.memory.memory_path).as_posix()
            stats = self._file_stat(path)
            files[relative] = stats
            if relative in MEMORY_FILES.values():
                memory_files[relative] = stats
        return {
            "created_at": now_ksa().isoformat(timespec="seconds"),
            "backup_name": backup_name,
            "files": files,
            "memory_files": memory_files,
        }

    def _memory_file_stats(self) -> dict[str, dict[str, Any]]:
        out = {}
        for filename in MEMORY_FILES.values():
            path = self.memory.memory_path / filename
            if path.is_file():
                out[filename] = self._file_stat(path)
        return out

    def _file_stat(self, path: Path) -> dict[str, Any]:
        content = path.read_bytes()
        text = content.decode("utf-8", errors="ignore")
        nonempty_lines = [line for line in text.splitlines() if line.strip()]
        return {
            "size": len(content),
            "lines": len(nonempty_lines),
            "sha1": hashlib.sha1(content).hexdigest(),
        }

    def _check_memory_shrinkage(
        self,
        previous: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
        report: IntegrityReport,
    ) -> None:
        for filename, old in previous.items():
            new = current.get(filename)
            if not new:
                continue
            old_size = int(old.get("size") or 0)
            new_size = int(new.get("size") or 0)
            if old_size < 500:
                continue
            if new_size < old_size * 0.5:
                report.critical.append(f"{filename} shrank from {old_size} bytes to {new_size} bytes")
            elif new_size < old_size * 0.75:
                report.warnings.append(f"{filename} shrank from {old_size} bytes to {new_size} bytes")

    def _check_summary_cache(self, report: IntegrityReport) -> None:
        summaries = self.memory.memory_path / ".summaries"
        for category, filename in MEMORY_FILES.items():
            source = self.memory.memory_path / filename
            meta = summaries / f"{category}.meta.json"
            if not source.is_file() or not meta.is_file():
                continue
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                report.warnings.append(f"Summary metadata is unreadable: {category}")
                continue
            source_hash = hashlib.sha1(source.read_bytes()).hexdigest()
            if data.get("source_hash") != source_hash:
                report.warnings.append(f"Summary cache is stale: {category}")

    def _check_reminders(self, report: IntegrityReport) -> None:
        now = now_ksa().replace(tzinfo=None)
        for reminder in self.memory.get_reminder_section():
            remind_at = reminder.get("remind_at", "")
            repeat = reminder.get("repeat", "none") or "none"
            if repeat not in RECURRING_REPEATS and repeat not in {"none", "countdown", "annual_countdown"}:
                report.warnings.append(f"Reminder has unknown repeat '{repeat}': {reminder['text']}")
            try:
                remind_dt = datetime.strptime(remind_at, DATETIME_FORMAT)
            except ValueError:
                report.warnings.append(f"Reminder has invalid remind_at: {reminder['text']}")
                continue
            if repeat == "none" and remind_dt < now - timedelta(days=2):
                report.warnings.append(f"One-time reminder is stale: {reminder['text']} ({remind_at})")
            if self._looks_like_stale_one_off_recurring(reminder, now):
                report.critical.append(f"One-off meeting reminder is still recurring: {reminder['text']}")

    def _looks_like_stale_one_off_recurring(self, reminder: dict, now: datetime) -> bool:
        repeat = reminder.get("repeat", "none")
        if repeat not in RECURRING_REPEATS or not reminder.get("event_at"):
            return False
        text = reminder.get("text", "").lower()
        if not any(term in text for term in ONE_OFF_EVENT_TERMS):
            return False
        try:
            event_dt = datetime.strptime(reminder["event_at"], DATETIME_FORMAT)
        except ValueError:
            return False
        return event_dt.date() < now.date()

    def _check_backup_freshness(self, report: IntegrityReport) -> None:
        backups = sorted(self.backup_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime)
        if not backups:
            report.info.append("No backup archive exists yet.")
            return
        latest = datetime.fromtimestamp(backups[-1].stat().st_mtime, tz=now_ksa().tzinfo)
        age = now_ksa() - latest
        if age > timedelta(hours=36):
            report.warnings.append(f"Latest backup is older than 36 hours: {backups[-1].name}")

    def _prune_backups(self) -> None:
        cutoff = datetime.now().timestamp() - self.retention_days * 24 * 60 * 60
        backups = sorted(self.backup_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime)
        remove = [path for path in backups if path.stat().st_mtime < cutoff]
        if len(backups) - len(remove) > self.max_backups:
            remove.extend(backups[: len(backups) - len(remove) - self.max_backups])
        for backup in set(remove):
            manifest = self._manifest_path_for_backup(backup)
            for path in (backup, manifest):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    log.debug(f"Could not prune backup {path}: {exc}")
