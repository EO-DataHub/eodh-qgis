"""HubClient fallback through the QGIS network stack.

QGIS requests honour the proxy (including PAC and proxy sign-in), certificate and
authentication settings configured in QGIS and the operating system, which
Python's urllib may not. Responses stream like urllib's, so large downloads are
never held in memory. Requests run on the calling (task) thread.
"""

import time
from http.client import HTTPMessage
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit

from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtCore import QByteArray, QEventLoop, QTimer, QUrl
from qgis.PyQt.QtNetwork import (
    QNetworkProxy,
    QNetworkProxyFactory,
    QNetworkProxyQuery,
    QNetworkReply,
    QNetworkRequest,
)

from eodh_qgis.api.hub import HubError, proxy_address

REDIRECTS = (301, 302, 303, 307, 308)


def text(value):
    """Header values arrive as str or QByteArray, depending on the PyQt version."""
    return value if isinstance(value, str) else bytes(value or b"").decode("latin-1")


class QgisNetwork:
    name = "QGIS network"

    def route(self, url):
        try:
            query = QNetworkProxyQuery(QUrl(url))
            manager = QgsNetworkAccessManager.instance()
            factory = manager.proxyFactory()
            proxies = factory.queryProxy(query) if factory else []
            proxy = proxies[0] if proxies else manager.proxy()
            if proxy.type() == QNetworkProxy.ProxyType.DefaultProxy and not proxy.hostName():
                # Resolved like Qt does: the application proxy or the system settings.
                proxy = next(iter(QNetworkProxyFactory.proxyForQuery(query)), proxy)
            if proxy.type() == QNetworkProxy.ProxyType.NoProxy or not proxy.hostName():
                return "direct"
            return "proxy " + proxy_address(f"{proxy.hostName()}:{proxy.port()}")
        except Exception as error:
            return f"proxy settings unreadable: {error}"

    def open(self, req, timeout):
        url, method, data = req.full_url, req.get_method(), req.data
        headers = dict(req.header_items())
        for _ in range(10):
            reply = Reply(url, method, headers, data, timeout)
            status = reply.status()
            if status not in REDIRECTS:
                break
            reply.close()
            target = urljoin(url, reply.header("Location"))
            # Same rules as SafeRedirect in hub.py.
            if urlsplit(target).scheme != "https":
                raise HubError("Refusing an insecure redirect.")
            if urlsplit(target).netloc != urlsplit(url).netloc:
                headers.pop("Authorization", None)
            if status == 303 or (status in (301, 302) and method == "POST"):
                method, data = "GET", None
                headers.pop("Content-type", None)
            elif method not in ("GET", "HEAD"):
                raise HTTPError(url, status, "Redirect of a non-GET request refused", reply.headers(), BytesIO())
            url = target
        else:
            raise URLError("too many redirects")
        if status >= 400:
            body = reply.read(check=False)
            reply.close()
            raise HTTPError(url, status, reply.reason(), reply.headers(), BytesIO(body))
        return Response(reply, url, status)


class Reply:
    """A QNetworkReply driven by a local event loop, so it can be read synchronously."""

    def __init__(self, url, method, headers, data, timeout):
        self.timeout = timeout
        request = QNetworkRequest(QUrl(url))
        for name, value in headers.items():
            request.setRawHeader(name.encode("latin-1"), value.encode("latin-1"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.ManualRedirectPolicy
        )
        # Authenticated EODH responses must never reach the QGIS disk cache.
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute, QNetworkRequest.CacheLoadControl.AlwaysNetwork
        )
        request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
        manager = QgsNetworkAccessManager.instance()
        if method == "GET":
            self.reply = manager.get(request)
        elif method == "POST":
            self.reply = manager.post(request, QByteArray(data or b""))
        else:
            self.reply = manager.sendCustomRequest(request, method.encode(), QByteArray(data or b""))
        # Bound memory for large downloads: Qt pauses reading when the buffer is full.
        self.reply.setReadBufferSize(8 * 1024 * 1024)
        self.loop = QEventLoop()
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.loop.quit)
        for signal in (self.reply.metaDataChanged, self.reply.readyRead, self.reply.finished):
            signal.connect(self.loop.quit)
        # Like urllib's timeout, this limits inactivity, not the length of a download.
        self.active = time.monotonic()
        self.reply.downloadProgress.connect(self.touch)
        self.reply.uploadProgress.connect(self.touch)
        self.wait(lambda: self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) is not None)

    def touch(self, *args):
        self.active = time.monotonic()

    def wait(self, ready):
        while not ready() and not self.reply.isFinished():
            remaining = self.active + self.timeout - time.monotonic()
            if remaining <= 0:
                self.close()
                raise TimeoutError("timed out")
            self.timer.start(int(remaining * 1000) + 1)
            self.loop.exec()
        self.timer.stop()

    def failure(self):
        """The network error, when the transfer failed rather than returning an HTTP response."""
        error = self.reply.error()
        if error == QNetworkReply.NetworkError.NoError:
            return None
        return f"{self.reply.errorString()} ({getattr(error, 'name', error)})"

    def status(self):
        status = self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status is None:
            failure = self.failure()
            self.close()
            raise URLError(failure or "no response")
        return int(status)

    def reason(self):
        return text(self.reply.attribute(QNetworkRequest.Attribute.HttpReasonPhraseAttribute))

    def header(self, name):
        return text(self.reply.rawHeader(name.encode()))

    def headers(self):
        message = HTTPMessage()
        for name, value in self.reply.rawHeaderPairs():
            message[text(name)] = text(value)
        return message

    def read(self, size=-1, check=True):
        if size < 0:
            # Drain while waiting: Qt stops receiving once its bounded buffer is full.
            chunks = []
            while True:
                self.wait(lambda: self.reply.bytesAvailable() > 0)
                chunks.append(bytes(self.reply.readAll()))
                if self.reply.isFinished() and not self.reply.bytesAvailable():
                    break
            data = b"".join(chunks)
        else:
            self.wait(lambda: self.reply.bytesAvailable() >= size)
            # PyQt6 returns None instead of b"" at the end of a finished reply.
            data = bytes(self.reply.read(size) or b"")
        # A transfer that broke off must not look like a complete, shorter file.
        # HTTP error responses also set an error, so their bodies skip this check.
        if check and self.reply.isFinished() and not self.reply.bytesAvailable() and (failure := self.failure()):
            raise ConnectionError(failure)
        return data

    def close(self):
        self.timer.stop()
        if not self.reply.isFinished():
            self.reply.abort()
        self.reply.deleteLater()


class Response:
    """The subset of urllib's response interface that HubClient uses."""

    def __init__(self, reply, url, status):
        self.reply, self.url, self.status = reply, url, status
        self.headers = reply.headers()

    def read(self, size=-1):
        return self.reply.read(size)

    def close(self):
        self.reply.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
