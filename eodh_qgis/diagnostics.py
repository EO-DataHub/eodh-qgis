"""Support diagnostics: readable errors, recent tracebacks and a copyable debug report.

Bug reports usually arrive as a screenshot, so errors name their cause and the
Debug info dialog collects everything else. Nothing here may contain the API key.
"""

import json
import os
import platform
import re
import ssl
import sys
import traceback
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request

from osgeo import gdal, osr
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsNetworkAccessManager, QgsProject
from qgis.PyQt import QtCore
from qgis.PyQt.QtNetwork import QNetworkProxyFactory, QNetworkProxyQuery, QSslSocket

from eodh_qgis.api.hub import (
    ENVIRONMENTS,
    NETWORK_ERRORS,
    HubError,
    PythonNetwork,
    network_reason,
    proxy_address,
    strip_queries,
)
from eodh_qgis.api.qgis_network import QgisNetwork

ERRORS_KEY = "eodh/recent_errors"
MAX_ERRORS = 20
LOG_TAGS = ("EODH", "Network")
PROBE_PATH = "/api/catalogue/stac/"

_secrets = set()
_log = deque(maxlen=60)
_previous_hook = None


def add_secret(value):
    if value:
        _secrets.add(value)


def redact(text):
    for secret in _secrets:
        text = text.replace(secret, "[redacted]")
    return strip_queries(re.sub(r"(?i)(bearer\s+)\S+", r"\1[redacted]", text))


def describe(error):
    """One line that identifies a failure: messages meant for users, otherwise type and location."""
    if isinstance(error, HubError) or type(error) is ValueError:
        return redact(str(error))
    frames = traceback.extract_tb(error.__traceback__)
    ours = [frame for frame in frames if "eodh_qgis" in frame.filename] or frames
    where = f" at {Path(ours[-1].filename).name}:{ours[-1].lineno} in {ours[-1].name}" if ours else ""
    return redact(f"Unexpected error: {type(error).__name__}: {error}{where}")


def recent_errors():
    try:
        errors = json.loads(QtCore.QSettings().value(ERRORS_KEY, "[]") or "[]")
        return errors if isinstance(errors, list) else []
    except ValueError:
        return []


def record(context, error):
    """Keep the error and its traceback across QGIS restarts, for the debug report."""
    entry = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "context": context,
        "message": describe(error),
        "traceback": redact("".join(traceback.format_exception(type(error), error, error.__traceback__)))[-6000:],
    }
    QtCore.QSettings().setValue(ERRORS_KEY, json.dumps([entry, *recent_errors()][:MAX_ERRORS]))


def log(message, level=Qgis.MessageLevel.Info):
    QgsMessageLog.logMessage(redact(message), "EODH", level, notifyUser=False)


def _log_received(message, tag, level):
    if tag in LOG_TAGS:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        _log.append(f"{stamp} [{tag}] {getattr(level, 'name', level)}: {redact(message)}")


def _excepthook(kind, value, tb):
    try:
        if any("eodh_qgis" in frame.filename for frame in traceback.extract_tb(tb)):
            record("Unhandled error", value)
    finally:
        (_previous_hook or sys.__excepthook__)(kind, value, tb)


def install():
    """Capture uncaught plugin errors and EODH/network log messages while the plugin is loaded."""
    global _previous_hook
    if sys.excepthook is not _excepthook:
        _previous_hook = sys.excepthook
        sys.excepthook = _excepthook
    QgsApplication.messageLog().messageReceived.connect(_log_received)


def uninstall():
    global _previous_hook
    if sys.excepthook is _excepthook:
        sys.excepthook = _previous_hook or sys.__excepthook__
    _previous_hook = None
    try:
        QgsApplication.messageLog().messageReceived.disconnect(_log_received)
    except TypeError:
        pass


def plugin_version():
    try:
        from qgis.utils import pluginMetadata

        version = pluginMetadata("eodh_qgis", "version")
        if version and version != "__error__":
            return version
    except ImportError:
        pass
    for folder in (Path(__file__).parent, Path(__file__).parents[1]):
        metadata = folder / "metadata.txt"
        if metadata.is_file():
            match = re.search(r"^version=(.+)$", metadata.read_text(encoding="utf-8"), re.MULTILINE)
            if match:
                return match.group(1).strip()
    return "unknown"


def operating_system():
    return QtCore.QSysInfo.prettyProductName() or platform.platform()


def environment_line():
    """Versions that belong in every screenshot of an error."""
    return (
        f"EODH plugin {plugin_version()} · QGIS {Qgis.version()} · Python {platform.python_version()} · "
        f"GDAL {gdal.__version__} · {operating_system()}"
    )


def probe(network, base=ENVIRONMENTS["Production"]):
    """Connect to the public EODH catalogue through one network path."""
    url = base + PROBE_PATH
    route = network.route(url)
    started = datetime.now(timezone.utc)
    try:
        with network.open(Request(url, headers={"Accept": "application/json"}), timeout=20) as response:
            response.read(1)
            outcome = f"HTTP {response.status}"
    except HubError as error:
        outcome = f"failed: {error}"
    except NETWORK_ERRORS as error:
        status = getattr(error, "code", None)
        outcome = f"HTTP {status}" if status else f"failed: {network_reason(error)}"
    seconds = (datetime.now(timezone.utc) - started).total_seconds()
    return f"{outcome} in {seconds:.1f} s ({route})"


def probe_gdal(base=ENVIRONMENTS["Production"]):
    """Raster streaming uses GDAL's libcurl, with its own proxy and certificate settings."""
    source = "/vsicurl?use_head=no&url=" + base + PROBE_PATH
    for key, value in (("GDAL_HTTP_TIMEOUT", "20"), ("GDAL_HTTP_CONNECTTIMEOUT", "10")):
        gdal.SetThreadLocalConfigOption(key, value)
    gdal.ErrorReset()
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        gdal.VSICurlPartialClearCache(source)
        stat = gdal.VSIStatL(source)
        return "reachable" if stat is not None else f"failed: {gdal.GetLastErrorMsg() or 'no response'}"
    finally:
        gdal.PopErrorHandler()
        for key in ("GDAL_HTTP_TIMEOUT", "GDAL_HTTP_CONNECTTIMEOUT"):
            gdal.SetThreadLocalConfigOption(key, None)


PROBES = {
    "Python": lambda: probe(PythonNetwork()),
    "QGIS network": lambda: probe(QgisNetwork()),
    "GDAL (raster streaming)": probe_gdal,
}


def _value(compute):
    try:
        value = compute()
    except Exception as error:
        return f"unavailable ({type(error).__name__}: {error})"
    return "—" if value in (None, "") else str(value)


def _section(title, rows):
    lines = ["", f"== {title} =="]
    width = max((len(name) for name, _ in rows), default=0)
    lines += [f"{name.ljust(width)} : {_value(compute)}" for name, compute in rows]
    return lines


def _without_credentials(value):
    return re.sub(r"//[^/@\s]+@", "//[credentials]@", value)


def _python_proxies():
    proxies = urllib.request.getproxies()
    return ", ".join(f"{scheme}={proxy_address(url)}" for scheme, url in sorted(proxies.items())) or "none"


def _global_opener():
    # QGIS's MetaSearch plugin replaces urllib.urlopen's opener when a QGIS proxy is
    # enabled. The plugin builds its own opener, so console tests can differ from it.
    opener = urllib.request._opener  # type: ignore[attr-defined]
    if opener is None:
        return "default"
    proxies = [
        getattr(handler, "proxies", {})
        for handler in opener.handlers
        if isinstance(handler, urllib.request.ProxyHandler)
    ]
    return f"replaced by another plugin (proxies: {_without_credentials(str(proxies))})"


def _environment_variables():
    names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    )
    found = {key: _without_credentials(value) for key, value in os.environ.items() if key.upper() in names}
    return ", ".join(f"{key}={value}" for key, value in sorted(found.items())) or "none"


def _qgis_proxy():
    manager = QgsNetworkAccessManager.instance()
    proxy = manager.fallbackProxy()
    kind = "system settings" if manager.useSystemProxy() else getattr(proxy.type(), "name", proxy.type())
    host = f" {proxy.hostName()}:{proxy.port()}" if proxy.hostName() else ""
    excluded = ", ".join(manager.excludeList()) or "none"
    direct = ", ".join(manager.noProxyList()) or "none"
    return f"{kind}{host} (excluded URLs: {excluded}; no-proxy URLs: {direct})"


def _system_proxy(base):
    proxies = QNetworkProxyFactory.systemProxyForQuery(QNetworkProxyQuery(QtCore.QUrl(base)))
    return ", ".join(
        f"{getattr(p.type(), 'name', p.type())} {p.hostName()}:{p.port()}" if p.hostName() else "direct"
        for p in proxies
    )


def _gdal_options():
    names = ("GDAL_HTTP_PROXY", "GDAL_HTTPS_PROXY", "GDAL_HTTP_PROXYUSERPWD", "GDAL_HTTP_UNSAFESSL", "CURL_CA_BUNDLE")
    values = {name: gdal.GetConfigOption(name) for name in names}
    return (
        ", ".join(
            f"{name}={'[set]' if name.endswith('USERPWD') else _without_credentials(value)}"
            for name, value in values.items()
            if value
        )
        or "none"
    )


def _active_plugins():
    from qgis.utils import active_plugins, pluginMetadata

    return ", ".join(f"{name} {pluginMetadata(name, 'version')}" for name in sorted(active_plugins, key=str.casefold))


def _eodh_layers():
    lines = []
    for layer in QgsProject.instance().mapLayers().values():
        remote = layer.customProperty("eodh/remote_url", "")
        if not remote and not layer.name().startswith("Quick view"):
            continue
        source = urlsplit(remote)
        where = f"streamed from {source.hostname}{source.path}" if remote else layer.providerType()
        lines.append(f"{layer.name()} ({where}, {'valid' if layer.isValid() else 'INVALID'})")
    return "; ".join(lines) or "none"


def report(dock=None, connectivity=None):
    """Plain-text debug report. The API key is never included."""
    client = getattr(dock, "client", None)
    if client is not None:
        add_secret(client.token)
    base = client.base if client is not None else ENVIRONMENTS["Production"]
    errors = recent_errors()
    lines = [
        "EODH QGIS plugin — debug info",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        environment_line(),
    ]
    lines += _section(
        "Summary",
        [
            ("Signed in", lambda: f"yes, workspace {client.workspace} at {client.base}" if client else "no"),
            ("Network in use", lambda: client.network if client else "not connected"),
            (
                "Last error",
                lambda: f"{errors[0]['time']} {errors[0]['context']}: {errors[0]['message']}" if errors else "none",
            ),
            ("Login message", lambda: dock.login.error.text() if dock and not dock.login.error.isHidden() else ""),
            ("Status", lambda: f"{dock.status.text()} {dock.status_detail.text()}".strip() if dock and client else ""),
        ],
    )
    lines += _section(
        "Connectivity to " + base + PROBE_PATH,
        [(name, lambda name=name: (connectivity or {}).get(name, "not tested")) for name in PROBES],
    )
    lines += _section(
        "Versions",
        [
            ("Plugin", plugin_version),
            ("Plugin folder", lambda: Path(__file__).parent),
            ("QGIS", lambda: f"{Qgis.version()} ({Qgis.devVersion()})"),
            ("Qt / PyQt", lambda: f"{QtCore.qVersion()} / {QtCore.PYQT_VERSION_STR}"),
            ("Python", lambda: f"{sys.version} ({sys.executable})"),
            ("GDAL", lambda: f"{gdal.__version__} (per-path HTTP options: {hasattr(gdal, 'SetPathSpecificOption')})"),
            (
                "PROJ",
                lambda: f"{osr.GetPROJVersionMajor()}.{osr.GetPROJVersionMinor()}.{osr.GetPROJVersionMicro()}",
            ),
            ("GEOS", Qgis.geosVersion),
            ("OpenSSL (Python)", lambda: ssl.OPENSSL_VERSION),
            ("TLS library (Qt)", QSslSocket.sslLibraryVersionString),
        ],
    )
    lines += _section(
        "System",
        [
            ("Operating system", operating_system),
            ("Platform", lambda: f"{platform.platform()} {platform.machine()}"),
            ("Locale", lambda: f"{QtCore.QLocale().name()}, UTC offset {datetime.now().astimezone().strftime('%z')}"),
            ("QGIS profile", QgsApplication.qgisSettingsDirPath),
        ],
    )
    lines += _section(
        "Network settings",
        [
            ("Python proxies", _python_proxies),
            ("Python CA paths", ssl.get_default_verify_paths),
            ("urllib.urlopen opener", _global_opener),
            ("Environment", _environment_variables),
            ("QGIS proxy", _qgis_proxy),
            ("QGIS route to EODH", lambda: QgisNetwork().route(base)),
            ("System proxy (Qt)", lambda: _system_proxy(base)),
            ("GDAL options", _gdal_options),
        ],
    )
    lines += _section(
        "QGIS",
        [
            ("Active plugins", _active_plugins),
            ("Project layers", lambda: len(QgsProject.instance().mapLayers())),
            ("EODH layers", _eodh_layers),
            ("Saved login", lambda: "yes" if dock and dock.auth_id else "no"),
        ],
    )
    lines += ["", f"== Recent errors ({len(errors)}, newest first) =="]
    for entry in errors:
        lines += [
            "",
            f"{entry.get('time')} — {entry.get('context')}",
            entry.get("message", ""),
            entry.get("traceback", ""),
        ]
    lines += ["", f"== Recent log messages ({', '.join(LOG_TAGS)}) =="]
    lines += list(_log) or ["none"]
    return redact("\n".join(str(line).rstrip() for line in lines))
