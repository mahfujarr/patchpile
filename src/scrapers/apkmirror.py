# ---------------------------------------------------------
# Copyright (C) 2026 krvstek (Original Author)
# Copyright (C) 2026 The uni-apks Contributors (Modifications)
#
# DO NOT REMOVE OR ALTER THIS COPYRIGHT HEADER.
# This file is part of uni-apks.
# Canonical source: https://github.com/krvstek/uni-apks
#
# Licensed under the GNU GPLv3. You may modify this file,
# but you MUST keep this original copyright notice intact
# and prominently state any changes made.
# See the AUTHORS file in the root directory for details.
# ---------------------------------------------------------

import re  # noqa: I001
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.core.network import NetworkManager, ResourceNotFoundError
from src.scrapers.base import (
    AppMetadata,
    BaseScraper,
    DownloadResult,
    ScraperError,
    _parse_html,
)

_DEFAULT_ARCH: frozenset[str] = frozenset(
    {"universal", "noarch", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi"}
)


class APKMirrorError(ScraperError):
    pass


class APKMirrorScraper(BaseScraper):
    def __init__(self, net: NetworkManager) -> None:
        super().__init__(net)
        self._category: str = ""
        self._release_urls: dict[str, str] = {}

    @staticmethod
    def _is_secondary(text: str) -> bool:
        """Return True when an APKMirror release is a SECONDARY build."""
        return bool(re.search(r"\bSECONDARY\b", text, re.IGNORECASE))

    @staticmethod
    def _extract_version(text: str) -> str | None:
        match = re.search(
            r"(?<![\d.])(\d+(?:\.\d+)+)(?![\d.-])",
            text,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    @classmethod
    def _matches_version(cls, text: str, version: str) -> bool:
        if cls._is_secondary(text):
            return False
        extracted = cls._extract_version(text)
        return extracted == version

    def fetch_metadata(self, url: str) -> AppMetadata:
        resp_html = self.net.get(url)
        self._category = url.rstrip("/").split("/")[-1]

        # Get package name from the app page.
        m = re.search(
            r"play\.google\.com/store/apps/details\?id=([\w.]+)",
            resp_html,
        )
        if not m:
            raise APKMirrorError("Package name not found")

        package_name = m.group(1)

        uploads_url = f"https://www.apkmirror.com/uploads/?appcategory={self._category}"

        soup = _parse_html(self.net.get(uploads_url))

        versions: list[str] = []
        for a in soup.select("#primary a.fontBlack[href*='-release/']"):
            text = a.get_text(" ", strip=True)
            href = a.get("href")
            if not href:
                continue
            if self._is_secondary(text):
                continue
            version = self._extract_version(text)
            if version is None:
                continue
            release_url = urljoin(
                "https://www.apkmirror.com",
                str(href),
            )
            self._release_urls[version] = release_url
            if version not in versions:
                versions.append(version)
        return AppMetadata(
            pkg_name=package_name,
            versions=versions,
        )

    def download(
        self,
        url: str,
        version: str,
        dest: Path,
        arch: str,
        dpi: str,
    ) -> DownloadResult:
        release_url = self._release_urls.get(version)
        if release_url is None:
            search_url = f"{url.rstrip('/')}/?s={version}"
            search_html = self.net.get(search_url)
            soup = _parse_html(search_html)
            for a in soup.select("a.fontBlack[href*='-release/']"):
                text = a.get_text(" ", strip=True)
                href = a.get("href")

                if not href:
                    continue
                if self._is_secondary(text):
                    continue
                if not self._matches_version(text, version):
                    continue
                if f"/{self._category}/" not in str(href):
                    continue
                release_url = urljoin("https://www.apkmirror.com", str(href))
                break

        if release_url is None:
            raise APKMirrorError("Version not found")

        try:
            release_html = self.net.get(release_url)
        except ResourceNotFoundError:
            raise APKMirrorError("Version not found") from None

        is_bundle = False
        soup_release = _parse_html(release_html)
        if soup_release.select_one("div.table-row.headerFont:last-child"):
            dl_url = self._pick_variant(soup_release, dpi, arch)
            if dl_url is None:
                raise APKMirrorError("No matching variant found")
            release_html = self.net.get(dl_url[0])
            is_bundle = dl_url[1] == "BUNDLE"

        soup_dl = _parse_html(release_html)
        btn = soup_dl.select_one("a.btn")
        if not btn or not btn.get("href"):
            raise APKMirrorError("Download button not found")
        btn_url = urljoin(
            "https://www.apkmirror.com",
            str(btn["href"]),
        )

        # Final APKMirror download page.
        soup_final = _parse_html(self.net.get(btn_url))
        dl_link = soup_final.select_one("span > a[rel=nofollow]")

        if not dl_link or not dl_link.get("href"):
            raise APKMirrorError("Final download link not found")

        final_url = urljoin(
            "https://www.apkmirror.com",
            str(dl_link["href"]),
        )
        out_path = dest.with_suffix(".apkm") if is_bundle else dest

        self.net.download(
            final_url,
            out_path,
        )

        return DownloadResult(
            path=out_path,
            is_bundle=is_bundle,
        )

    def _pick_variant(
        self,
        soup: BeautifulSoup,
        dpi: str,
        arch: str,
    ) -> tuple[str, str] | None:
        apparch: set[str] = set(_DEFAULT_ARCH)
        if arch != "all":
            apparch.add(arch)

        rows = soup.select("div.table-row.headerFont")
        # Prefer normal APK first, then BUNDLE.
        for bundle_type in ("APK", "BUNDLE"):
            for row in reversed(rows):
                cells = row.select("div.table-cell")
                if len(cells) < 4:
                    continue

                link = cells[0].select_one("a")
                if not link or not link.get("href"):
                    continue

                badge = cells[0].select_one(".apkm-badge")
                b_type = badge.get_text(strip=True).upper() if badge else "APK"

                arch_text = cells[1].get_text(strip=True)
                dpi_text = cells[3].get_text(strip=True)

                dpi_ok = (
                    not dpi_text
                    or bool(
                        re.match(
                            r"\d+-640dpi",
                            dpi_text,
                        )
                    )
                    or dpi_text
                    in {
                        "nodpi",
                        "anydpi",
                    }
                    or (bool(dpi) and dpi_text == dpi)
                )

                if b_type == bundle_type and arch_text in apparch and dpi_ok:
                    return (
                        urljoin(
                            "https://www.apkmirror.com",
                            str(link["href"]),
                        ),
                        bundle_type,
                    )
        return None
