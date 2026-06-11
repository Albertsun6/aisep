"""spec: specs/feat-launcher-outputs 验收 5 — 启动台零外呼与注入式 API 静态探针(纯 stdlib)。"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "docs" / "sdlc-launcher.html"


class TestLauncherStaticProbes(unittest.TestCase):
    def _text(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_all_refs_relative(self):
        from html.parser import HTMLParser

        found = []

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                for k, v in attrs:
                    if k in ("src", "href") and v:
                        found.append((tag, v))

        P().feed(self._text())
        self.assertTrue(any(v == "launcher-data.js" for _, v in found))  # 数据脚本在且相对
        for tag, url in found:
            self.assertFalse(url.startswith(("http:", "https:", "//")), f"{tag} 外呼: {url}")

    def test_no_network_api_calls(self):
        text = self._text()
        for token in ("fetch(", "XMLHttpRequest", "sendBeacon", "import("):
            self.assertNotIn(token, text, f"页面不应含网络调用 {token}")

    def test_no_injection_apis_zero_exemption(self):
        """验收 5 核心:五 token 全禁、含注释——本页渲染任何 PR 都能改的 specs 全文。"""
        text = self._text()
        for token in ("innerHTML", "outerHTML", "insertAdjacentHTML",
                      "document.write", "setHTMLUnsafe"):
            self.assertNotIn(token, text, f"注入式 API token 不得出现: {token}")

    def test_no_absolute_urls_flat_ban(self):
        """平坦禁令:整页无 http(s):// 字样(现状即满足;要豁免先改 spec 走行级 allowlist)。"""
        text = self._text()
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)


if __name__ == "__main__":
    unittest.main()
