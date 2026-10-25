"""Read public GitHub releases with a process-local, nonblocking update cache."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from functools import total_ordering
from time import monotonic
from typing import Any
from urllib.parse import quote, urlsplit

import httpx2

from version import VERSION

REPOSITORY = "wudahua/MCP_CREO_MechDog"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASE_ROOT = f"https://github.com/{REPOSITORY}/releases"
CACHE_SECONDS = 24 * 60 * 60
RETRY_SECONDS = 15 * 60
NETWORK_SECONDS = 5
MAX_PAGES = 20
MAX_PAGE_BYTES = 4 * 1024 * 1024
_SEMVER = re.compile(
    r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
    re.ASCII,
)


@total_ordering
class SemanticVersion:
    """SemVer precedence, including rc identifiers; build metadata is ignored."""

    def __init__(self, value: str):
        match = _SEMVER.fullmatch(value)
        if match is None:
            raise ValueError("Invalid semantic version")
        self.core = tuple(int(match[i]) for i in (1, 2, 3))
        self.pre = tuple((match[4] or "").split(".")) if match[4] else ()
        if any(item.isdigit() and len(item) > 1 and item[0] == "0" for item in self.pre):
            raise ValueError("Numeric prerelease identifiers cannot have leading zeroes")
        self.text = value.removeprefix("v")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self.core == other.core and self.pre == other.pre

    def __lt__(self, other: SemanticVersion) -> bool:
        if self.core != other.core:
            return self.core < other.core
        if not self.pre or not other.pre:
            return bool(self.pre) and not other.pre
        for left, right in zip(self.pre, other.pre):
            if left == right:
                continue
            if left.isdigit() and right.isdigit():
                return int(left) < int(right)
            if left.isdigit() != right.isdigit():
                return left.isdigit()
            return left < right
        return len(self.pre) < len(other.pre)


class UpdateFailure(Exception):
    """A public, sanitized failure reason, never a raw network exception."""


def _official_url(value: Any, prefix: str) -> str | None:
    if not isinstance(value, str) or not value.startswith(prefix):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return None
    return value


def select_release(releases: list[dict[str, Any]], current: str) -> dict[str, Any]:
    """Select the highest comparable published release, independent of list ordering."""
    try:
        local = SemanticVersion(current)
    except ValueError:
        return {"status": "unknown", "message": "当前版本格式无法比较，无法确认更新。"}
    candidates = []
    for release in releases:
        if not isinstance(release, dict):
            raise UpdateFailure("GitHub Release 列表包含非预期数据。")
        if release.get("draft") is not False or not release.get("published_at"):
            continue
        published = release["published_at"]
        try:
            published_time = datetime.fromisoformat(published)
            if published_time.tzinfo is None:
                raise ValueError("Missing publication timezone")
        except (ValueError, TypeError):
            raise UpdateFailure("GitHub Release 的发布时间无效。") from None
        if published_time > datetime.now(timezone.utc):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            continue
        try:
            version = SemanticVersion(tag)
        except ValueError:
            continue
        if not isinstance(release.get("prerelease"), bool):
            raise UpdateFailure("GitHub Release 的预发布标记无效。")
        candidates.append((version, release))
    if not candidates:
        return {"status": "unknown", "message": "没有可比较的公开发布版本，无法确认更新。"}
    latest, release = max(candidates, key=lambda item: item[0])
    release_url = _official_url(release.get("html_url"), RELEASE_ROOT + "/tag/")
    release_url = release_url or RELEASE_ROOT + "/tag/" + quote(release["tag_name"], safe="")
    download_url = release_url
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise UpdateFailure("GitHub Release 的附件列表无效。")
    expected = f"MCP_CREO_MechDog-{latest.text}-source.zip"
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == expected:
            official = _official_url(asset.get("browser_download_url"), RELEASE_ROOT + "/download/")
            if official and asset.get("state") == "uploaded":
                download_url = official
                break
    available = local < latest
    prerelease = release["prerelease"]
    if available:
        qualifier = "（预发布）" if prerelease else ""
        message = (
            f"MCP_CREO_MechDog 有新版本：当前 {current}，新版 {latest.text}{qualifier}。"
            "请查看版本说明和下载链接。等待建模完成后停止 MCP 服务，保留本机配置、模型和任务记录，"
            "更新源码并使用目标 Creo 对应的 SDK 重新运行 setup.ps1，然后重启 MCP 服务。"
        )
    elif latest < local:
        message = "当前版本高于最高公开版本，无需降级。"
    else:
        message = "当前版本已是最高可比较的公开版本。"
    return {
        "status": "update_available" if available else "up_to_date",
        "latest_version": latest.text,
        "is_prerelease": prerelease,
        "release_url": release_url,
        "download_url": download_url,
        "message": message,
    }


async def fetch_releases() -> list[dict[str, Any]]:
    """Fetch all pages within one five-second budget; never accept a partial list."""
    releases = []
    async with httpx2.AsyncClient(
        timeout=NETWORK_SECONDS,
        follow_redirects=False,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"MCP_CREO_MechDog/{VERSION}",
        },
    ) as client:
        for page in range(1, MAX_PAGES + 1):
            async with client.stream(
                "GET", API_URL, params={"per_page": 100, "page": page}
            ) as response:
                if response.status_code != 200:
                    reason = "（可能限流）" if response.status_code in (403, 429) else ""
                    raise UpdateFailure(
                        f"GitHub 更新检查失败：HTTP {response.status_code}{reason}。"
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_PAGE_BYTES:
                        raise UpdateFailure("GitHub Release 响应超过大小限制，无法确认更新。")
                try:
                    entries = json.loads(body)
                except (ValueError, UnicodeError):
                    raise UpdateFailure("GitHub Release 响应不是有效 JSON。") from None
                if not isinstance(entries, list) or len(entries) > 100:
                    raise UpdateFailure("GitHub Release 响应不是有效分页列表。")
                releases.extend(entries)
                # Follow pagination even when a short page advertises a next page.
                if "next" not in response.links and len(entries) < 100:
                    return releases
    raise UpdateFailure("GitHub Release 分页超过安全上限，未使用不完整列表判断最新版。")


class UpdateChecker:
    """One shared async request per service; no disk cache or model/config writes."""

    def __init__(self, current_version: str = VERSION):
        self.current_version = current_version
        self._result: dict[str, Any] = {
            "status": "not_checked",
            "current_version": current_version,
            "latest_version": None,
            "is_prerelease": None,
            "release_url": None,
            "download_url": None,
            "checked_at": None,
            "last_success_at": None,
            "message": "更新检查尚未开始。",
            "error": None,
        }
        self._expires = 0.0
        self._success_expires = 0.0
        self._inflight: asyncio.Task | None = None
        self._background: asyncio.Task | None = None

    def snapshot(self, *, from_cache: bool = True) -> dict[str, Any]:
        result = dict(self._result)
        if self._inflight is not None and not self._inflight.done():
            result["status"] = "checking"
            result["message"] = "正在检查更新；已有版本信息来自缓存。"
        result["from_cache"] = from_cache
        result["stale"] = bool(result["latest_version"]) and (
            monotonic() >= self._success_expires or result["error"] is not None
        )
        return result

    async def check(self, force: bool = False) -> dict[str, Any]:
        if self._inflight is not None and not self._inflight.done():
            await asyncio.shield(self._inflight)
            return self.snapshot(from_cache=False)
        valid = monotonic() < self._expires
        # Even explicit refresh respects the failure cooldown to avoid retry storms.
        if valid and (not force or self._result["status"] in ("failed", "unknown")):
            return self.snapshot()
        self._inflight = asyncio.create_task(self._refresh())
        await asyncio.shield(self._inflight)
        return self.snapshot(from_cache=False)

    async def _refresh(self) -> None:
        try:
            async with asyncio.timeout(NETWORK_SECONDS):
                releases = await fetch_releases()
                selected = select_release(releases, self.current_version)
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx2.TimeoutException):
            selected = {"status": "failed", "error": "GitHub 更新检查超过 5 秒网络预算。"}
        except UpdateFailure as exc:
            selected = {"status": "failed", "error": str(exc)}
        except Exception:
            # Proxy addresses, local certificate paths and credentials must never escape.
            selected = {"status": "failed", "error": "GitHub 更新检查网络或响应处理失败。"}
        now = datetime.now(timezone.utc).isoformat()
        if selected["status"] == "failed":
            self._result.update(selected, checked_at=now)
            if self._result.get("latest_version"):
                # A failed check never claims "up to date"; retained successful
                # data is stale cache only and must be read with status/error.
                self._result["message"] = (
                    "未取得最新版本信息：本次更新检查失败，不代表已是最新版本；"
                    "15 分钟后可重试。latest_version 等字段仅为上次成功取得的过期缓存，"
                    "须结合 status=failed、stale 与 error 使用。"
                )
            else:
                self._result["message"] = (
                    "未取得最新版本信息：本次更新检查失败，不代表已是最新版本；15 分钟后可重试。"
                )
            self._expires = monotonic() + RETRY_SECONDS
            return
        self._result.update(
            latest_version=None,
            is_prerelease=None,
            release_url=None,
            download_url=None,
            error=None,
            checked_at=now,
            last_success_at=None if selected["status"] == "unknown" else now,
        )
        self._result.update(selected)
        self._expires = monotonic() + (
            RETRY_SECONDS if selected["status"] == "unknown" else CACHE_SECONDS
        )
        self._success_expires = self._expires

    def start(self) -> None:
        if self._background is None or self._background.done():
            self._background = asyncio.create_task(self._poll())

    async def _poll(self) -> None:
        while True:
            await self.check()
            await asyncio.sleep(max(1, self._expires - monotonic()))

    async def stop(self) -> None:
        tasks = [task for task in (self._background, self._inflight) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
