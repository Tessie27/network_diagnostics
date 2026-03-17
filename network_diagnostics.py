"""
Network Diagnostics Tool
Author: Tezz
Requires: Python 3.8+ standard library only (no pip)
"""

import platform
import re
import socket
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

# Colours
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#21262d"
BORDER    = "#30363d"
FG        = "#e6edf3"
FG_DIM    = "#8b949e"
GREEN     = "#3fb950"
BLUE      = "#58a6ff"
ORANGE    = "#f0883e"
RED       = "#f85149"
PURPLE    = "#bc8cff"
YELLOW    = "#e3b341"


def ts():
    return datetime.now().strftime("%H:%M:%S")


def is_windows():
    return platform.system() == "Windows"


class NetworkTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Network Diagnostics Tool")
        self.geometry("860x700")
        self.minsize(700, 560)
        self.configure(bg=BG)
        try:
            self.iconphoto(True, tk.PhotoImage(file="web.png"))
        except Exception:
            pass
        self._running = False
        self._build_ui()

    # UI
    def _build_ui(self):
        self._style()

        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="Network Diagnostics", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=FG).pack(side="left")
        self.status_dot = tk.Label(hdr, text="●", font=("Segoe UI", 14),
                                   bg=BG, fg=FG_DIM)
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_lbl = tk.Label(hdr, text="Ready", font=("Segoe UI", 11),
                                   bg=BG, fg=FG_DIM)
        self.status_lbl.pack(side="right")

        # Target input bar
        bar = tk.Frame(self, bg=BG2, bd=0, highlightbackground=BORDER,
                       highlightthickness=1)
        bar.pack(fill="x", padx=20, pady=12)

        tk.Label(bar, text="Target", font=("Segoe UI", 11),
                 bg=BG2, fg=FG_DIM, width=7).pack(side="left", padx=(12, 0))

        self.target_var = tk.StringVar(value="8.8.8.8")
        entry = tk.Entry(bar, textvariable=self.target_var,
                         font=("Segoe UI", 12), bg=BG3, fg=FG,
                         insertbackground=FG, relief="flat",
                         highlightbackground=BORDER, highlightthickness=1)
        entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        entry.bind("<Return>", lambda e: self._run_all())

        tk.Label(bar, text="Port", font=("Segoe UI", 11),
                 bg=BG2, fg=FG_DIM).pack(side="left")
        self.port_var = tk.StringVar(value="80")
        port_entry = tk.Entry(bar, textvariable=self.port_var,
                              font=("Segoe UI", 12), bg=BG3, fg=FG,
                              insertbackground=FG, relief="flat",
                              highlightbackground=BORDER, highlightthickness=1,
                              width=6)
        port_entry.pack(side="left", padx=(6, 10), pady=8)

        self.run_btn = tk.Button(bar, text="Run All", font=("Segoe UI", 11, "bold"),
                                 bg=GREEN, fg="#0d1117", relief="flat",
                                 padx=16, pady=6, cursor="hand2",
                                 command=self._run_all)
        self.run_btn.pack(side="left", padx=(0, 12))

        # Diagnostics buttons row
        diag_row = tk.Frame(self, bg=BG)
        diag_row.pack(fill="x", padx=20, pady=(0, 4))
        tk.Label(diag_row, text="Diagnostics", font=("Segoe UI", 9),
                 bg=BG, fg=FG_DIM, width=10, anchor="w").pack(side="left")
        for label, cmd in [
            ("Ping",       self._run_ping),
            ("Traceroute", self._run_traceroute),
            ("DNS Lookup", self._run_dns),
            ("Port Check", self._run_port),
            ("My IP Info", self._run_myip),
            ("Clear",      self._clear),
        ]:
            tk.Button(diag_row, text=label, font=("Segoe UI", 10),
                      bg=BG3, fg=FG, relief="flat",
                      padx=12, pady=4, cursor="hand2",
                      activebackground=BORDER, activeforeground=FG,
                      command=cmd).pack(side="left", padx=(0, 6))

        # Fixes buttons row
        fix_row = tk.Frame(self, bg=BG)
        fix_row.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(fix_row, text="Fixes", font=("Segoe UI", 9),
                 bg=BG, fg=FG_DIM, width=10, anchor="w").pack(side="left")
        for label, cmd in [
            ("Flush DNS",       self._flush_dns),
            ("Release / Renew", self._release_renew),
            ("Reset Winsock",   self._reset_winsock),
            ("Reset IP Stack",  self._reset_ip_stack),
            ("Reset All",       self._reset_all),
        ]:
            tk.Button(fix_row, text=label, font=("Segoe UI", 10),
                      bg="#1a0a0a", fg=ORANGE, relief="flat",
                      padx=12, pady=4, cursor="hand2",
                      highlightbackground=BORDER, highlightthickness=1,
                      activebackground=BG3, activeforeground=ORANGE,
                      command=cmd).pack(side="left", padx=(0, 6))

        # Output area
        out_frame = tk.Frame(self, bg=BG2, bd=0,
                             highlightbackground=BORDER, highlightthickness=1)
        out_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.output = scrolledtext.ScrolledText(
            out_frame, font=("Consolas", 11), bg=BG2, fg=FG,
            insertbackground=FG, relief="flat", wrap="word",
            padx=14, pady=12, state="disabled",
            selectbackground=BG3
        )
        self.output.pack(fill="both", expand=True)

        # Tag colours
        self.output.tag_config("hdr",   foreground=BLUE,   font=("Consolas", 11, "bold"))
        self.output.tag_config("fix",   foreground=YELLOW, font=("Consolas", 11, "bold"))
        self.output.tag_config("ok",    foreground=GREEN)
        self.output.tag_config("warn",  foreground=ORANGE)
        self.output.tag_config("err",   foreground=RED)
        self.output.tag_config("dim",   foreground=FG_DIM)
        self.output.tag_config("ts",    foreground=PURPLE)
        self.output.tag_config("label", foreground=BLUE)

        self._write_welcome()

    def _style(self):
        ttk.Style(self).theme_use("default")

    # Output helpers
    def _write(self, text, tag=None):
        self.output.configure(state="normal")
        if tag:
            self.output.insert("end", text, tag)
        else:
            self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _writeln(self, text="", tag=None):
        self._write(text + "\n", tag)

    def _section(self, title, fix=False):
        self._writeln()
        self._write(f"[{ts()}] ", "ts")
        self._writeln(f"-- {title}", "fix" if fix else "hdr")

    def _clear(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._write_welcome()

    def _write_welcome(self):
        self._writeln("Network Diagnostics Tool  --  Tezz", "hdr")
        self._writeln("Diagnostics: enter a target and use the buttons above.", "dim")
        self._writeln("Fixes: flush DNS, release/renew IP, reset Winsock/IP stack.", "dim")
        self._writeln("Note: Fix commands require Administrator privileges.", "warn")
        self._writeln()

    def _set_status(self, text, color=FG_DIM):
        self.status_lbl.configure(text=text, fg=color)
        self.status_dot.configure(fg=color)

    def _set_busy(self, busy):
        self._running = busy
        state = "disabled" if busy else "normal"
        self.run_btn.configure(state=state)
        self._set_status("Running..." if busy else "Done",
                         ORANGE if busy else GREEN)

    def _run_admin_cmd(self, commands, section_title):
        """Run one or more shell commands and stream output, with admin elevation note."""
        def task():
            self._section(section_title, fix=True)
            if not is_windows():
                self._writeln("  Fix commands are Windows-only.", "warn")
                return
            for cmd in commands:
                self._write(f"  > {' '.join(cmd)}\n", "dim")
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=20,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    output = (result.stdout + result.stderr).strip()
                    for line in output.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if any(k in line.lower() for k in
                               ["success", "completed", "flushed", "registered", "ok"]):
                            self._writeln("  " + line, "ok")
                        elif any(k in line.lower() for k in
                                 ["error", "failed", "denied", "unable"]):
                            self._writeln("  " + line, "err")
                        else:
                            self._writeln("  " + line, "dim")
                    if result.returncode != 0:
                        self._writeln(
                            "  Command returned a non-zero exit code. "
                            "Try running as Administrator.", "warn"
                        )
                except subprocess.TimeoutExpired:
                    self._writeln("  Command timed out.", "err")
                except FileNotFoundError as e:
                    self._writeln(f"  Command not found: {e}", "err")
                except PermissionError:
                    self._writeln(
                        "  Permission denied. Right-click the app and run as Administrator.", "err"
                    )
        threading.Thread(target=task, daemon=True).start()

    # Fix actions
    def _flush_dns(self):
        self._run_admin_cmd(
            [["ipconfig", "/flushdns"]],
            "Flush DNS Cache"
        )

    def _release_renew(self):
        self._run_admin_cmd(
            [["ipconfig", "/release"], ["ipconfig", "/renew"]],
            "Release and Renew IP"
        )

    def _reset_winsock(self):
        if not messagebox.askyesno(
            "Reset Winsock",
            "This will reset the Winsock catalogue.\n"
            "A restart is required after.\n\nContinue?"
        ):
            return
        self._run_admin_cmd(
            [["netsh", "winsock", "reset"]],
            "Reset Winsock"
        )
        self._writeln("  Restart your PC for changes to take effect.", "warn")

    def _reset_ip_stack(self):
        if not messagebox.askyesno(
            "Reset IP Stack",
            "This will reset the TCP/IP stack.\n"
            "A restart is required after.\n\nContinue?"
        ):
            return
        self._run_admin_cmd(
            [["netsh", "int", "ip", "reset"]],
            "Reset TCP/IP Stack"
        )
        self._writeln("  Restart your PC for changes to take effect.", "warn")

    def _reset_all(self):
        if not messagebox.askyesno(
            "Full Network Reset",
            "This will run:\n"
            "  - ipconfig /flushdns\n"
            "  - ipconfig /release\n"
            "  - ipconfig /renew\n"
            "  - netsh winsock reset\n"
            "  - netsh int ip reset\n\n"
            "A restart will be required.\n\nContinue?"
        ):
            return
        self._run_admin_cmd(
            [
                ["ipconfig", "/flushdns"],
                ["ipconfig", "/release"],
                ["ipconfig", "/renew"],
                ["netsh", "winsock", "reset"],
                ["netsh", "int", "ip", "reset"],
            ],
            "Full Network Reset"
        )
        self._writeln("  All reset commands complete. Restart your PC.", "warn")

    # Run all diagnostics
    def _run_all(self):
        if self._running:
            return
        def task():
            self._set_busy(True)
            self._run_ping(threaded=False)
            self._run_dns(threaded=False)
            self._run_port(threaded=False)
            self._run_traceroute(threaded=False)
            self._set_busy(False)
        threading.Thread(target=task, daemon=True).start()

    # Ping
    def _run_ping(self, threaded=True):
        def task():
            target = self.target_var.get().strip()
            self._section(f"Ping  ->  {target}")
            flag = "-n" if is_windows() else "-c"
            try:
                result = subprocess.run(
                    ["ping", flag, "4", target],
                    capture_output=True, text=True, timeout=15
                )
                for line in (result.stdout or result.stderr).splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if any(k in line.lower() for k in ["reply from", "bytes from"]):
                        self._writeln("  " + line, "ok")
                    elif any(k in line.lower() for k in ["timeout", "unreachable", "failure"]):
                        self._writeln("  " + line, "err")
                    elif any(k in line.lower() for k in ["average", "avg", "packets"]):
                        self._writeln("  " + line, "label")
                    else:
                        self._writeln("  " + line, "dim")
                tag = "ok" if result.returncode == 0 else "err"
                msg = "Host is reachable." if result.returncode == 0 else "Host did not respond."
                self._writeln("  " + msg, tag)
            except subprocess.TimeoutExpired:
                self._writeln("  Ping timed out.", "err")
        if threaded:
            threading.Thread(target=task, daemon=True).start()
        else:
            task()

    # DNS Lookup
    def _run_dns(self, threaded=True):
        def task():
            target = self.target_var.get().strip()
            self._section(f"DNS Lookup  ->  {target}")
            try:
                results = socket.getaddrinfo(target, None)
                seen = set()
                for r in results:
                    ip = r[4][0]
                    family = "IPv6" if r[0].name == "AF_INET6" else "IPv4"
                    if ip not in seen:
                        seen.add(ip)
                        self._write(f"  {family:<6}  ", "label")
                        self._writeln(ip, "ok")
                try:
                    hostname = socket.gethostbyaddr(target)[0]
                    self._write("  Reverse  ", "label")
                    self._writeln(hostname, "ok")
                except Exception:
                    pass
                self._writeln(f"  Resolved {len(seen)} address(es).", "dim")
            except socket.gaierror as e:
                self._writeln(f"  DNS resolution failed: {e}", "err")
        if threaded:
            threading.Thread(target=task, daemon=True).start()
        else:
            task()

    # Port Check
    def _run_port(self, threaded=True):
        def task():
            target = self.target_var.get().strip()
            try:
                port = int(self.port_var.get().strip())
            except ValueError:
                self._writeln("  Invalid port number.", "err")
                return
            self._section(f"Port Check  ->  {target}:{port}")
            common = {
                21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
                53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
                443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
                5985: "WinRM", 8080: "HTTP-alt", 8443: "HTTPS-alt",
            }
            self._write("  Service:  ", "label")
            self._writeln(common.get(port, "Unknown"), "dim")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                r = sock.connect_ex((target, port))
                sock.close()
                if r == 0:
                    self._writeln(f"  Port {port} is OPEN.", "ok")
                else:
                    self._writeln(f"  Port {port} is CLOSED or filtered.", "warn")
            except socket.gaierror:
                self._writeln("  Could not resolve hostname.", "err")
            except Exception as e:
                self._writeln(f"  Error: {e}", "err")
            self._writeln()
            self._writeln("  Quick scan -- common ports:", "label")
            for qp in [22, 80, 443, 3389, 445]:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    r = s.connect_ex((target, qp))
                    s.close()
                    status = "open  " if r == 0 else "closed"
                    self._write(f"    {qp:<6} {common.get(qp, ''):<10}  ", "dim")
                    self._writeln(status, "ok" if r == 0 else "dim")
                except Exception:
                    self._writeln(f"    {qp:<6} error", "err")
        if threaded:
            threading.Thread(target=task, daemon=True).start()
        else:
            task()

    # Traceroute
    def _run_traceroute(self, threaded=True):
        def task():
            target = self.target_var.get().strip()
            self._section(f"Traceroute  ->  {target}")
            self._writeln("  This may take up to 30 seconds...", "dim")
            cmd = ["tracert", "-d", "-h", "20", target] if is_windows() \
                  else ["traceroute", "-n", "-m", "20", target]
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0
                )
                hop = 0
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line.strip():
                        continue
                    if any(k in line.lower() for k in ["tracing", "traceroute", "over a maximum"]):
                        self._writeln("  " + line.strip(), "dim")
                    elif "*" in line and re.match(r"\s*\d+", line):
                        self._writeln("  " + line.strip(), "warn")
                    elif re.match(r"\s*\d+", line):
                        hop += 1
                        self._writeln("  " + line.strip(), "ok")
                    else:
                        self._writeln("  " + line.strip(), "dim")
                proc.wait(timeout=35)
                self._writeln(f"  Trace complete. {hop} hop(s) recorded.", "label")
            except FileNotFoundError:
                self._writeln("  tracert/traceroute not available.", "err")
            except subprocess.TimeoutExpired:
                proc.kill()
                self._writeln("  Traceroute timed out.", "warn")
            except Exception as e:
                self._writeln(f"  Error: {e}", "err")
        if threaded:
            threading.Thread(target=task, daemon=True).start()
        else:
            task()

    # My IP Info
    def _run_myip(self):
        def task():
            self._section("My IP Info")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                self._write("  Local IP:     ", "label")
                self._writeln(local_ip, "ok")
            except Exception:
                self._writeln("  Could not determine local IP.", "err")
            try:
                self._write("  Hostname:     ", "label")
                self._writeln(socket.gethostname(), "ok")
            except Exception:
                pass
            try:
                if is_windows():
                    r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5)
                    for line in r.stdout.splitlines():
                        if "Default Gateway" in line:
                            gw = line.split(":")[-1].strip()
                            if gw:
                                self._write("  Gateway:      ", "label")
                                self._writeln(gw, "ok")
                                break
            except Exception:
                pass
            try:
                if is_windows():
                    r = subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         "Get-DnsClientServerAddress -AddressFamily IPv4 | "
                         "Select-Object -ExpandProperty ServerAddresses"],
                        capture_output=True, text=True, timeout=6
                    )
                    dns = [line.strip() for line in r.stdout.splitlines() if line.strip()]
                    if dns:
                        self._write("  DNS Servers:  ", "label")
                        self._writeln(", ".join(dns[:4]), "ok")
            except Exception:
                pass
        threading.Thread(target=task, daemon=True).start()


def main():
    app = NetworkTool()
    app.mainloop()


if __name__ == "__main__":
    main()
