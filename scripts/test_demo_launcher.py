"""Проверки запуска демо без интернета, аккаунтов и внешней публикации."""
import sys
import unittest
from unittest.mock import MagicMock, patch

import start_demo as demo


class DemoLauncherTests(unittest.TestCase):
    def release(self, **changes):
        asset = {"name": demo.ASSET_NAME, "digest": "sha256:" + "a" * 64, "size": 1234, "browser_download_url": "https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/" + demo.ASSET_NAME}
        asset.update(changes)
        return {"assets": [asset]}

    def test_official_asset_requires_digest_and_exact_owner(self):
        _, digest, size = demo.release_asset(self.release())
        self.assertEqual(digest, "a" * 64)
        self.assertEqual(size, 1234)
        for changes in ({"digest": None}, {"digest": "sha256:bad"}, {"browser_download_url": "https://example.com/" + demo.ASSET_NAME}, {"size": 0}, {"size": 129 * 1024 * 1024}):
            with self.subTest(changes=changes), self.assertRaises((RuntimeError, TypeError)):
                demo.release_asset(self.release(**changes))

    def test_extracts_only_cloudflare_hostname(self):
        self.assertEqual(demo.tunnel_origin("| https://green-demo.trycloudflare.com |\n"), "https://green-demo.trycloudflare.com")
        for line in ("https://green-demo.trycloudflare.com.evil.test", "http://green-demo.trycloudflare.com", "https://trycloudflare.com", "https://green-demo.trycloudflare.com:443"):
            self.assertIsNone(demo.tunnel_origin(line))

    def test_declining_never_downloads_or_starts_external_access(self):
        server = MagicMock()
        server.store.admin_configured.return_value = True
        with patch.object(sys, "argv", ["start_demo.py", "--no-browser"]), patch.object(demo, "LocalCmsServer", return_value=server) as factory, patch.object(demo.threading, "Thread"), patch("builtins.input", return_value="нет"), patch.object(demo, "install_tunnel") as download, patch.object(demo, "start_tunnel") as tunnel:
            demo.main()
        factory.assert_called_once_with(("127.0.0.1", 8346), demo.ROOT / "site", demo.DEMO_DATA, cookie_prefix="dm_demo")
        download.assert_not_called()
        tunnel.assert_not_called()
        server.set_public_origin.assert_not_called()
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()

    def test_prepare_only_never_starts_tunnel(self):
        server = MagicMock()
        with patch.object(sys, "argv", ["start_demo.py", "--no-browser", "--prepare-only"]), patch.object(demo, "LocalCmsServer", return_value=server), patch.object(demo.threading, "Thread"), patch.object(demo.time, "sleep", side_effect=KeyboardInterrupt), patch.object(demo, "install_tunnel") as download, patch.object(demo, "start_tunnel") as tunnel:
            demo.main()
        download.assert_not_called()
        tunnel.assert_not_called()
        server.set_public_origin.assert_not_called()
        server.shutdown.assert_called_once()

    def test_unconfigured_account_cannot_skip_local_setup(self):
        server = MagicMock()
        server.store.admin_configured.return_value = False
        with patch.object(sys, "argv", ["start_demo.py", "--no-browser"]), patch.object(demo, "LocalCmsServer", return_value=server), patch.object(demo.threading, "Thread"), patch("builtins.input", side_effect=EOFError), patch.object(demo, "install_tunnel") as download, patch.object(demo, "start_tunnel") as tunnel:
            with self.assertRaises(EOFError):
                demo.main()
        download.assert_not_called()
        tunnel.assert_not_called()
        server.set_public_origin.assert_not_called()
        server.server_close.assert_called_once()

    def test_failed_external_check_closes_tunnel_and_server(self):
        server = MagicMock()
        server.store.admin_configured.return_value = True
        process = MagicMock()
        with patch.object(sys, "argv", ["start_demo.py", "--no-browser"]), patch.object(demo, "LocalCmsServer", return_value=server), patch.object(demo.threading, "Thread"), patch("builtins.input", return_value="ДА"), patch.object(demo, "install_tunnel", return_value=demo.TOOLS / "cloudflared.exe"), patch.object(demo, "start_tunnel", return_value=(process, "https://green-demo.trycloudflare.com")), patch.object(demo, "check_external", return_value=False), patch.object(demo, "stop_tunnel") as stop:
            with self.assertRaises(RuntimeError):
                demo.main()
        server.set_public_origin.assert_called_once_with("https://green-demo.trycloudflare.com")
        stop.assert_called_once_with(process)
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
