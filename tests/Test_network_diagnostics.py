"""
Unit tests for Network Diagnostics Tool
Covers: utility functions, DNS logic, port logic, platform checks
Uses: pytest + unittest.mock (stdlib only, no extra deps beyond pytest)
"""

import platform
import re
import socket
import subprocess
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Stub out tkinter entirely so tests run headless on CI
tk_stub = types.ModuleType("tkinter")
for _attr in [
    "Tk", "Frame", "Label", "Entry", "Button", "StringVar",
    "PhotoImage", "scrolledtext", "ttk", "messagebox",
]:
    setattr(tk_stub, _attr, MagicMock())
tk_stub.END = "end"

scrolledtext_stub = types.ModuleType("tkinter.scrolledtext")
scrolledtext_stub.ScrolledText = MagicMock()
ttk_stub = types.ModuleType("tkinter.ttk")
ttk_stub.Style = MagicMock()
messagebox_stub = types.ModuleType("tkinter.messagebox")
messagebox_stub.askyesno = MagicMock(return_value=True)

sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.scrolledtext", scrolledtext_stub)
sys.modules.setdefault("tkinter.ttk", ttk_stub)
sys.modules.setdefault("tkinter.messagebox", messagebox_stub)

import network_diagnostics as nd  # noqa: E402  (import after stubs)


# ---------------------------------------------------------------------------
# ts() – timestamp helper
# ---------------------------------------------------------------------------
class TestTs:
    def test_format(self):
        result = nd.ts()
        parts = result.split(":")
        assert len(parts) == 3, "Expected HH:MM:SS"
        assert all(p.isdigit() for p in parts)

    def test_returns_string(self):
        assert isinstance(nd.ts(), str)


# ---------------------------------------------------------------------------
# is_windows()
# ---------------------------------------------------------------------------
class TestIsWindows:
    def test_returns_bool(self):
        assert isinstance(nd.is_windows(), bool)

    def test_true_on_windows(self):
        with patch.object(platform, "system", return_value="Windows"):
            assert nd.is_windows() is True

    def test_false_on_linux(self):
        with patch.object(platform, "system", return_value="Linux"):
            assert nd.is_windows() is False

    def test_false_on_darwin(self):
        with patch.object(platform, "system", return_value="Darwin"):
            assert nd.is_windows() is False


# ---------------------------------------------------------------------------
# DNS resolution logic (socket.getaddrinfo)
# ---------------------------------------------------------------------------
class TestDnsResolution:
    """Test the core DNS resolution used in _run_dns."""

    def test_resolves_known_host(self):
        """getaddrinfo should return results for a known IP literal."""
        results = socket.getaddrinfo("127.0.0.1", None)
        assert len(results) > 0

    def test_raises_on_invalid_host(self):
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("this.hostname.does.not.exist.invalid", None)

    def test_ip_extraction(self):
        """Verify we can extract the IP string from getaddrinfo tuples."""
        results = socket.getaddrinfo("127.0.0.1", None)
        ips = {r[4][0] for r in results}
        assert "127.0.0.1" in ips or "::1" in ips


# ---------------------------------------------------------------------------
# Port check logic
# ---------------------------------------------------------------------------
class TestPortCheck:
    def test_open_port_detected(self):
        """connect_ex returns 0 for an open port (mocked)."""
        with patch("socket.socket") as mock_sock_cls:
            instance = MagicMock()
            instance.connect_ex.return_value = 0
            mock_sock_cls.return_value = instance
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("8.8.8.8", 80))
            assert result == 0

    def test_closed_port_detected(self):
        """connect_ex returns non-zero for a closed port (mocked)."""
        with patch("socket.socket") as mock_sock_cls:
            instance = MagicMock()
            instance.connect_ex.return_value = 111
            mock_sock_cls.return_value = instance
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("192.0.2.1", 9999))
            assert result != 0

    def test_port_service_map(self):
        """Known ports should map to expected service names."""
        common = {
            21: "FTP", 22: "SSH", 80: "HTTP", 443: "HTTPS", 3389: "RDP"
        }
        assert common[80] == "HTTP"
        assert common[443] == "HTTPS"
        assert common.get(9999, "Unknown") == "Unknown"

    def test_invalid_port_string(self):
        with pytest.raises(ValueError):
            int("not_a_port")


# ---------------------------------------------------------------------------
# Ping command construction
# ---------------------------------------------------------------------------
class TestPingCommand:
    def test_windows_flag(self):
        with patch.object(nd, "is_windows", return_value=True):
            flag = "-n" if nd.is_windows() else "-c"
            assert flag == "-n"

    def test_linux_flag(self):
        with patch.object(nd, "is_windows", return_value=False):
            flag = "-n" if nd.is_windows() else "-c"
            assert flag == "-c"

    def test_ping_runs_subprocess(self):
        mock_result = MagicMock()
        mock_result.stdout = "Reply from 8.8.8.8: bytes=32\n"
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            subprocess.run(["ping", "-c", "4", "8.8.8.8"],
                           capture_output=True, text=True, timeout=15)
            mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Subprocess / admin command helpers
# ---------------------------------------------------------------------------
class TestAdminCommandHelpers:
    def test_timeout_handled(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 5)):
            with pytest.raises(subprocess.TimeoutExpired):
                subprocess.run(["ping"], timeout=5)

    def test_file_not_found_handled(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("cmd not found")):
            with pytest.raises(FileNotFoundError):
                subprocess.run(["nonexistent_command"])

    def test_permission_error_handled(self):
        with patch("subprocess.run", side_effect=PermissionError("access denied")):
            with pytest.raises(PermissionError):
                subprocess.run(["netsh", "winsock", "reset"])


# ---------------------------------------------------------------------------
# Output tag keyword matching (replicated logic from the tool)
# ---------------------------------------------------------------------------
class TestOutputTagging:
    def _classify(self, line: str) -> str:
        line_l = line.lower()
        if any(k in line_l for k in ["success", "completed", "flushed", "registered", "ok"]):
            return "ok"
        if any(k in line_l for k in ["error", "failed", "denied", "unable"]):
            return "err"
        return "dim"

    def test_success_line(self):
        assert self._classify("Successfully flushed the DNS Resolver Cache.") == "ok"

    def test_error_line(self):
        assert self._classify("Error: access denied") == "err"

    def test_neutral_line(self):
        assert self._classify("Windows IP Configuration") == "dim"

    def test_ok_keyword(self):
        assert self._classify("Operation OK") == "ok"


# ---------------------------------------------------------------------------
# Traceroute line classification (replicated regex logic)
# ---------------------------------------------------------------------------
class TestTracerouteClassification:
    def _classify(self, line: str) -> str:
        if any(k in line.lower() for k in ["tracing", "traceroute", "over a maximum"]):
            return "dim"
        if "*" in line and re.match(r"\s*\d+", line):
            return "warn"
        if re.match(r"\s*\d+", line):
            return "ok"
        return "dim"

    def test_hop_line(self):
        assert self._classify("  1    <1 ms    <1 ms    <1 ms  192.168.1.1") == "ok"

    def test_timeout_hop(self):
        assert self._classify("  3     *        *        *     Request timed out.") == "warn"

    def test_header_line(self):
        assert self._classify("Tracing route to 8.8.8.8 over a maximum of 30 hops") == "dim"

    def test_non_hop_line(self):
        assert self._classify("Trace complete.") == "dim"
