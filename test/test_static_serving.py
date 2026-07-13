from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test.optional_stubs import install_curl_cffi_stub, install_fastapi_stubs, install_pil_stub, install_pybase64_stub, install_pydantic_stub, install_starlette_stub, install_tiktoken_stub

install_curl_cffi_stub()
install_fastapi_stubs()
install_pil_stub()
install_pybase64_stub()
install_pydantic_stub()
install_starlette_stub()
install_tiktoken_stub()

from api import app as app_module
from api import support


class StaticServingTests(unittest.TestCase):
    def setUp(self) -> None:
        support.web_dist_base_dir.cache_clear()
        support.web_index_asset.cache_clear()
        self.addCleanup(support.web_dist_base_dir.cache_clear)
        self.addCleanup(support.web_index_asset.cache_clear)

    def test_root_and_index_use_cached_index_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            web_dist = Path(temp_dir)
            index = web_dist / "index.html"
            index.write_text("ok", encoding="utf-8")

            with mock.patch.object(support, "WEB_DIST_DIR", web_dist):
                self.assertEqual(support.resolve_web_asset(""), index)
                self.assertEqual(support.resolve_web_asset("index.html"), index)
                with mock.patch.object(Path, "is_file", side_effect=AssertionError("cached index should not stat again")):
                    self.assertEqual(support.resolve_web_asset(""), index)
                    self.assertEqual(support.resolve_web_asset("index.html"), index)

    def test_fallback_uses_precomputed_index_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            web_dist = Path(temp_dir)
            index = web_dist / "index.html"
            index.write_text("ok", encoding="utf-8")

            with mock.patch.object(support, "WEB_DIST_DIR", web_dist):
                response = app_module.serve_web_asset("missing-route")

            self.assertEqual(response.path, index)

    def test_next_missing_asset_remains_fast_404_without_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            web_dist = Path(temp_dir)
            (web_dist / "index.html").write_text("ok", encoding="utf-8")

            with mock.patch.object(support, "WEB_DIST_DIR", web_dist), mock.patch.object(app_module, "web_index_asset", wraps=app_module.web_index_asset) as index_asset:
                with self.assertRaises(app_module.HTTPException) as raised:
                    app_module.serve_web_asset("_next/static/missing.js")

            self.assertEqual(raised.exception.status_code, 404)
            index_asset.assert_not_called()
    def test_rejects_static_path_traversal(self) -> None:
        with TemporaryDirectory() as temp_dir:
            web_dist = Path(temp_dir) / "web_dist"
            web_dist.mkdir()
            outside = Path(temp_dir) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            (web_dist / "index.html").write_text("ok", encoding="utf-8")

            with mock.patch.object(support, "WEB_DIST_DIR", web_dist):
                self.assertIsNone(support.resolve_web_asset("../secret.txt"))
                self.assertIsNone(support.resolve_web_asset("nested/../../secret.txt"))


if __name__ == "__main__":
    unittest.main()
