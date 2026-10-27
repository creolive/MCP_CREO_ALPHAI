"""FEAT-020 deterministic version, network, cache and MCP integration guards."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx2

import server
from creo_mechdog import capability_pages
from creo_mechdog import update_check as updates


def release(tag="v0.3.0", *, prerelease=False, draft=False, published=True, assets=None):
    return {
        "tag_name": tag,
        "draft": draft,
        "published_at": "2026-10-14T00:00:00Z" if published else None,
        "prerelease": prerelease,
        "html_url": updates.RELEASE_ROOT + "/tag/" + tag,
        "assets": assets or [],
    }


class SemanticVersionTests(unittest.TestCase):
    def test_semver_precedence_and_numeric_rc_order(self):
        ordered = [
            "0.3.0-alpha",
            "0.3.0-alpha.1",
            "0.3.0-alpha.beta",
            "0.3.0-beta",
            "0.3.0-beta.2",
            "0.3.0-beta.11",
            "0.3.0-rc.1",
            "0.3.0-rc.2",
            "0.3.0-rc.10",
            "0.3.0",
            "0.3.1",
            "0.10.0",
            "1.0.0",
        ]
        values = [updates.SemanticVersion(value) for value in ordered]
        self.assertEqual(sorted(reversed(values)), values)
        for lower, higher in zip(values, values[1:]):
            self.assertLess(lower, higher)

    def test_prefix_and_build_metadata_do_not_change_precedence(self):
        self.assertEqual(updates.SemanticVersion("v0.3.0+dev.2"), updates.SemanticVersion("0.3.0"))

    def test_invalid_and_historical_labels_are_not_compared(self):
        for value in ("v0.22", "0.21", "0.3.0_20261014", "01.2.3", "0.3.0-rc.01", "0.3.0-", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                updates.SemanticVersion(value)

    def test_new_release_uses_official_source_asset(self):
        url = updates.RELEASE_ROOT + "/download/v0.3.0/MCP_CREO_MechDog-0.3.0-source.zip"
        data = release(
            assets=[
                {
                    "name": "MCP_CREO_MechDog-0.3.0-source.zip",
                    "state": "uploaded",
                    "browser_download_url": url,
                }
            ]
        )
        result = updates.select_release([data], "0.2.6")
        self.assertEqual(result["status"], "update_available")
        self.assertEqual(result["download_url"], url)
        self.assertIn("保留本机配置", result["message"])

    def test_equal_and_development_versions_never_suggest_downgrade(self):
        for current in ("0.3.0", "0.3.0+dev", "0.4.0-rc.1"):
            result = updates.select_release([release()], current)
            self.assertEqual(result["status"], "up_to_date")
        self.assertIn("无需降级", result["message"])

    def test_prerelease_is_discovered_without_relying_on_date_or_order(self):
        data = [
            release("v0.3.0-rc.2", prerelease=True),
            release("v0.3.0-rc.10", prerelease=True),
            release("v0.2.6"),
        ]
        result = updates.select_release(data, "0.2.6")
        self.assertEqual(result["latest_version"], "0.3.0-rc.10")
        self.assertTrue(result["is_prerelease"])
        self.assertIn("预发布", result["message"])
        result = updates.select_release(data + [release()], "0.2.6")
        self.assertEqual(result["latest_version"], "0.3.0")

    def test_empty_draft_unpublished_and_unparseable_are_unknown(self):
        for data in ([], [release(draft=True)], [release(published=False)], [release("v0.22")]):
            self.assertEqual(updates.select_release(data, "0.2.6")["status"], "unknown")
        self.assertEqual(updates.select_release([release()], "bad")["status"], "unknown")

    def test_unsafe_asset_falls_back_to_release_page(self):
        data = release(
            assets=[
                {
                    "name": "MCP_CREO_MechDog-0.3.0-source.zip",
                    "state": "uploaded",
                    "browser_download_url": "https://github.com.evil.test/archive.zip",
                }
            ]
        )
        data["html_url"] = "https://evil.test/release"
        result = updates.select_release([data], "0.2.6")
        self.assertEqual(result["download_url"], updates.RELEASE_ROOT + "/tag/v0.3.0")

    def test_future_release_is_excluded_and_malformed_publication_fails(self):
        data = release()
        data["published_at"] = "2099-10-14T00:00:00Z"
        self.assertEqual(updates.select_release([data], "0.2.6")["status"], "unknown")
        for value in (True, "bad", "2026-10-14T00:00:00"):
            data["published_at"] = value
            with self.subTest(value=value), self.assertRaises(updates.UpdateFailure):
                updates.select_release([data], "0.2.6")


class UpdateCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.checker = updates.UpdateChecker("0.2.6")
        self.addAsyncCleanup(self.checker.stop)
        self.fetch = self.enterContext(
            patch.object(updates, "fetch_releases", new_callable=AsyncMock)
        )
        self.fetch.return_value = [release()]
        self.now = 100.0
        self.enterContext(patch.object(updates, "monotonic", side_effect=lambda: self.now))

    async def test_first_check_cache_and_force(self):
        self.assertEqual(self.checker.snapshot()["status"], "not_checked")
        result = await self.checker.check()
        self.assertEqual(result["status"], "update_available")
        self.assertFalse(result["from_cache"])
        self.assertFalse(result["stale"])
        self.assertEqual(result["current_version"], "0.2.6")
        self.assertEqual(result["checked_at"], result["last_success_at"])
        result = await self.checker.check()
        self.assertTrue(result["from_cache"])
        self.assertEqual(self.fetch.await_count, 1)
        await self.checker.check(force=True)
        self.assertEqual(self.fetch.await_count, 2)

    async def test_cache_expiry_refreshes_and_failed_refresh_retains_stale_data(self):
        original = await self.checker.check()
        self.now += updates.CACHE_SECONDS
        self.assertTrue(self.checker.snapshot()["stale"])
        self.fetch.side_effect = OSError("secret proxy/password/local certificate")
        failed = await self.checker.check()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["last_success_at"], original["last_success_at"])
        self.assertEqual(failed["download_url"], original["download_url"])
        self.assertTrue(failed["stale"])
        self.assertNotIn("secret", json.dumps(failed))
        await self.checker.check(force=True)
        self.assertEqual(self.fetch.await_count, 2)
        self.now += updates.RETRY_SECONDS
        self.fetch.side_effect = None
        self.assertEqual((await self.checker.check())["status"], "update_available")

    async def test_force_failure_marks_fresh_previous_success_stale(self):
        await self.checker.check()
        self.fetch.side_effect = updates.UpdateFailure("HTTP 429")
        result = await self.checker.check(force=True)
        self.assertEqual(result["error"], "HTTP 429")
        self.assertTrue(result["stale"])

    async def test_failure_messages_state_latest_info_was_not_obtained(self):
        # No prior success: latest_version stays null and the message must never
        # read as "already up to date".
        self.fetch.side_effect = OSError("network down")
        result = await self.checker.check()
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["latest_version"])
        self.assertIsNotNone(result["error"])
        self.assertIn("未取得最新版本信息", result["message"])
        self.assertIn("不代表已是最新版本", result["message"])
        self.assertIn("15 分钟后可重试", result["message"])
        self.assertEqual(
            result["message"].count("已是最新"),
            result["message"].count("不代表已是最新版本"),
        )
        # After a successful check, a failure keeps the stale cached target and
        # labels it as expired cache that must be read with status/stale/error.
        self.fetch.side_effect = None
        self.now += updates.RETRY_SECONDS
        original = await self.checker.check()
        self.assertEqual(original["status"], "update_available")
        self.fetch.side_effect = updates.UpdateFailure("HTTP 503")
        self.now += updates.CACHE_SECONDS
        failed = await self.checker.check()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["latest_version"], original["latest_version"])
        self.assertTrue(failed["stale"])
        self.assertIn("未取得最新版本信息", failed["message"])
        self.assertIn("过期缓存", failed["message"])
        self.assertIn("status=failed", failed["message"])

    async def test_no_data_uses_cooldown_and_does_not_claim_up_to_date(self):
        self.fetch.return_value = []
        result = await self.checker.check()
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["latest_version"])
        await self.checker.check(force=True)
        self.assertEqual(self.fetch.await_count, 1)
        self.now += updates.RETRY_SECONDS
        self.fetch.return_value = [release()]
        self.assertEqual((await self.checker.check())["status"], "update_available")

    async def test_concurrent_checks_share_request_and_cache_reads_do_not_wait(self):
        gate = asyncio.Event()
        started = asyncio.Event()

        async def blocked():
            started.set()
            await gate.wait()
            return [release()]

        self.fetch.side_effect = blocked
        first = asyncio.create_task(self.checker.check(force=True))
        await started.wait()
        second = asyncio.create_task(self.checker.check(force=True))
        with (
            patch.object(server, "updates", self.checker),
            patch.object(server, "startup") as startup,
        ):
            startup.status.return_value = {"state": "ready", "revision": 8}
            capability_pages.reset_snapshot()
            caps = await asyncio.wait_for(server.creo_capabilities(), 3.0)
            state = await asyncio.wait_for(server.creo_startup_status(), 0.5)
            self.assertEqual(caps["update"], state["update"])
            self.assertEqual(state["update"]["status"], "checking")
            self.assertEqual(state["state"], "ready")
            self.assertEqual(state["revision"], 8)
            self.assertFalse(first.done())
            with patch.object(
                server.general, "submit", return_value={"job_id": "fixture"}
            ) as submit:
                result = await asyncio.wait_for(server.creo_new_part(), 0.5)
                self.assertEqual(result["job_id"], "fixture")
                submit.assert_called_once()
                startup.require_ready.assert_called_once()
        gate.set()
        results = await asyncio.gather(first, second)
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.fetch.await_count, 1)

    async def test_caller_cancellation_does_not_cancel_shared_refresh(self):
        gate = asyncio.Event()
        started = asyncio.Event()

        async def blocked():
            started.set()
            await gate.wait()
            return [release()]

        self.fetch.side_effect = blocked
        caller = asyncio.create_task(self.checker.check())
        await started.wait()
        caller.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await caller
        self.assertFalse(self.checker._inflight.done())
        gate.set()
        result = await self.checker.check()
        self.assertEqual(result["status"], "update_available")

    async def test_total_deadline_and_lifespan_shutdown(self):
        gate = asyncio.Event()
        self.fetch.side_effect = gate.wait
        with patch.object(updates, "NETWORK_SECONDS", 0.02):
            result = await self.checker.check()
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["latest_version"])
        self.assertIn("预算", result["error"])
        self.now += updates.RETRY_SECONDS
        with (
            patch.object(server, "updates", self.checker),
            patch.object(server, "startup") as startup,
        ):
            async with server.server_lifespan(server.mcp):
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                self.assertEqual(self.checker.snapshot()["status"], "checking")
            startup.start.assert_called_once()
            startup.stop.assert_called_once()
        self.assertTrue(self.checker._inflight.done())
        self.assertTrue(self.checker._background.done())

    async def test_three_interfaces_share_contract_and_network_annotation(self):
        with (
            patch.object(server, "updates", self.checker),
            patch.object(server, "startup") as startup,
        ):
            startup.status.return_value = {"state": "ready"}
            await server.creo_check_update()
            direct = await server.creo_check_update()
            capability_pages.reset_snapshot()
            self.assertEqual(direct, (await server.creo_capabilities())["update"])
            self.assertEqual(direct, (await server.creo_startup_status())["update"])
            tools = {tool.name: tool for tool in await server.mcp.list_tools()}
            tool = tools["creo_check_update"]
            self.assertEqual(len(tools), 94)
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertTrue(tool.annotations.open_world_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertFalse(tool.input_schema["properties"]["force"]["default"])
            self.assertEqual(
                set(direct),
                {
                    "status",
                    "current_version",
                    "latest_version",
                    "is_prerelease",
                    "release_url",
                    "download_url",
                    "checked_at",
                    "last_success_at",
                    "from_cache",
                    "stale",
                    "message",
                    "error",
                },
            )


class GitHubResponseTests(unittest.IsolatedAsyncioTestCase):
    def client(self, handler):
        constructor = httpx2.AsyncClient
        return patch.object(
            updates.httpx2,
            "AsyncClient",
            side_effect=lambda **kwargs: constructor(
                transport=httpx2.MockTransport(handler), **kwargs
            ),
        )

    async def test_pagination_finds_higher_version_on_later_page(self):
        calls = []

        def handler(request):
            self.assertEqual(str(request.url).split("?")[0], updates.API_URL)
            self.assertNotIn("authorization", request.headers)
            calls.append(int(request.url.params["page"]))
            if len(calls) == 1:
                return httpx2.Response(200, json=[release("v0.2.6")] * 100)
            return httpx2.Response(200, json=[release("v0.4.0-rc.1", prerelease=True)])

        with self.client(handler):
            data = await updates.fetch_releases()
        self.assertEqual(calls, [1, 2])
        self.assertEqual(updates.select_release(data, "0.2.6")["latest_version"], "0.4.0-rc.1")

    async def test_short_page_next_link_does_not_redirect_to_external_host(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if len(calls) == 1:
                return httpx2.Response(
                    200,
                    json=[release("v0.2.6")],
                    headers={"Link": '<https://evil.test/private>; rel="next"'},
                )
            return httpx2.Response(200, json=[release()])

        with self.client(handler):
            data = await updates.fetch_releases()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(url.startswith(updates.API_URL) for url in calls))
        self.assertEqual(updates.select_release(data, "0.2.6")["status"], "update_available")

    async def test_network_errors_and_bad_responses_never_claim_latest(self):
        responses = [
            httpx2.Response(429),
            httpx2.Response(403),
            httpx2.Response(500),
            httpx2.Response(302, headers={"Location": "https://evil.test"}),
            httpx2.Response(200, content=b"invalid"),
            httpx2.Response(200, json={"message": "error"}),
            httpx2.Response(200, json=[None]),
        ]
        for response in responses:
            checker = updates.UpdateChecker("0.2.6")
            with self.subTest(code=response.status_code), self.client(lambda request: response):
                result = await checker.check()
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["latest_version"])
            await checker.stop()
        for error in (httpx2.ConnectError("secret"), httpx2.ReadTimeout("secret")):
            checker = updates.UpdateChecker("0.2.6")
            with self.client(Mock(side_effect=error)):
                result = await checker.check()
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("secret", json.dumps(result))
            await checker.stop()

    async def test_page_limits_and_partial_results_are_not_accepted(self):
        with (
            self.client(lambda request: httpx2.Response(200, json=[release()] * 100)),
            patch.object(updates, "MAX_PAGES", 2),
        ):
            with self.assertRaisesRegex(updates.UpdateFailure, "分页"):
                await updates.fetch_releases()
        with (
            self.client(lambda request: httpx2.Response(200, content=b" " * 100)),
            patch.object(updates, "MAX_PAGE_BYTES", 99),
        ):
            with self.assertRaisesRegex(updates.UpdateFailure, "大小"):
                await updates.fetch_releases()


if __name__ == "__main__":
    unittest.main()
