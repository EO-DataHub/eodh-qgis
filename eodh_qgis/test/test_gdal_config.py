"""Tests for GDAL vsicurl configuration."""

from __future__ import annotations

import json
import time
import unittest
import urllib.request

from osgeo import gdal

from eodh_qgis.gdal_config import (
    GDAL_VSICURL_OPTIONS,
    configure_gdal_vsicurl,
    restore_gdal_vsicurl,
)


class TestConfigureGdalVsicurl(unittest.TestCase):
    """Tests for configure/restore GDAL vsicurl options."""

    def tearDown(self):
        restore_gdal_vsicurl()

    def test_configure_sets_all_options(self):
        configure_gdal_vsicurl()
        for key, expected in GDAL_VSICURL_OPTIONS.items():
            self.assertEqual(gdal.GetConfigOption(key), expected, f"{key} not set")

    def test_restore_resets_options(self):
        originals = {k: gdal.GetConfigOption(k) for k in GDAL_VSICURL_OPTIONS}

        configure_gdal_vsicurl()
        restore_gdal_vsicurl()

        for key, original in originals.items():
            self.assertEqual(gdal.GetConfigOption(key), original, f"{key} not restored")

    def test_preserves_existing_values(self):
        gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "99")
        try:
            configure_gdal_vsicurl()
            self.assertEqual(gdal.GetConfigOption("GDAL_HTTP_MAX_RETRY"), "3")

            restore_gdal_vsicurl()
            self.assertEqual(gdal.GetConfigOption("GDAL_HTTP_MAX_RETRY"), "99")
        finally:
            gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", None)

    def test_options_has_expected_keys(self):
        expected = {
            "GDAL_DISABLE_READDIR_ON_OPEN",
            "VSI_CACHE",
            "VSI_CACHE_SIZE",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS",
            "GDAL_HTTP_MULTIRANGE",
            "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES",
            "GDAL_HTTP_MAX_RETRY",
            "GDAL_HTTP_RETRY_DELAY",
        }
        self.assertEqual(set(GDAL_VSICURL_OPTIONS.keys()), expected)


def _get_cog_url_from_stac() -> str | None:
    """Query EODH STAC API for a real Sentinel-2 COG URL."""
    stac_url = "https://eodatahub.org.uk/api/catalogue/stac/search?collections=sentinel2_ard&limit=1"
    try:
        with urllib.request.urlopen(stac_url, timeout=15) as resp:
            data = json.loads(resp.read())
        for feat in data.get("features", []):
            for asset in feat.get("assets", {}).values():
                if "tiff" in (asset.get("type") or ""):
                    return asset["href"]
    except Exception:
        pass
    return None


class TestVsicurlBenchmark(unittest.TestCase):
    """Performance benchmark: vsicurl with vs without GDAL config.

    Verifies that the configured options do not degrade performance
    compared to GDAL defaults.
    """

    @classmethod
    def setUpClass(cls):
        gdal.UseExceptions()
        cls.cog_url = _get_cog_url_from_stac()
        if not cls.cog_url:
            raise unittest.SkipTest("Could not fetch COG URL from STAC API")

    def _clear_config(self):
        for key in GDAL_VSICURL_OPTIONS:
            gdal.SetConfigOption(key, None)

    def _time_open(self, url: str) -> float:
        gdal.VSICurlClearCache()
        start = time.time()
        ds = gdal.Open(f"/vsicurl/{url}")
        elapsed = time.time() - start
        self.assertIsNotNone(ds, f"Failed to open {url}")
        ds = None
        return elapsed

    @staticmethod
    def _median(values: list[float]) -> float:
        s = sorted(values)
        return s[len(s) // 2]

    def test_benchmark_configured_not_slower(self):
        """Config options must not make layer loading slower."""
        runs = 5
        url = self.cog_url

        # Baseline: no config
        self._clear_config()
        baseline_times = [self._time_open(url) for _ in range(runs)]

        # Configured
        configure_gdal_vsicurl()
        try:
            configured_times = [self._time_open(url) for _ in range(runs)]
        finally:
            restore_gdal_vsicurl()
            self._clear_config()

        # Use median to resist network outliers
        median_baseline = self._median(baseline_times)
        median_configured = self._median(configured_times)

        # Allow 15% tolerance for network jitter
        self.assertLessEqual(
            median_configured,
            median_baseline * 1.15,
            f"Configured ({median_configured:.3f}s) is more than 15% slower "
            f"than baseline ({median_baseline:.3f}s). "
            f"Baseline runs: {baseline_times}, "
            f"Configured runs: {configured_times}",
        )


if __name__ == "__main__":
    unittest.main()
