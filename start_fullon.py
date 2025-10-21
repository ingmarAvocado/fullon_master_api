#!/usr/bin/env python3
"""
Fullon Master API Daemon Launcher

Manages the lifecycle of the Fullon Master API server as a daemon process.

Usage:
    ./start_fullon.py start    # Start the daemon
    ./start_fullon.py stop     # Stop the daemon
    ./start_fullon.py restart  # Restart the daemon
    ./start_fullon.py status   # Check daemon status
    ./start_fullon.py logs     # Tail daemon logs
"""
import sys
import os
import signal
import time
import argparse
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fullon_log import get_component_logger
from fullon_master_api.config import settings

logger = get_component_logger("fullon.master_api.daemon")

# Daemon configuration
DAEMON_NAME = "fullon_master_api"
PID_FILE = Path.home() / f".{DAEMON_NAME}.pid"
LOG_FILE = Path("/tmp") / f"{DAEMON_NAME}.log"


class DaemonManager:
    """Manages daemon lifecycle for Fullon Master API."""

    def __init__(self, pid_file: Path, log_file: Path):
        self.pid_file = pid_file
        self.log_file = log_file

    def get_pid(self) -> Optional[int]:
        """
        Get PID from pid file.

        Returns:
            int: PID if process is running
            None: If not running
        """
        if not self.pid_file.exists():
            return None

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())

            # Check if process is actually running
            os.kill(pid, 0)  # Doesn't kill, just checks existence
            return pid

        except (ValueError, ProcessLookupError, PermissionError):
            # PID file exists but process isn't running
            self.pid_file.unlink(missing_ok=True)
            return None

    def write_pid(self, pid: int):
        """Write PID to pid file."""
        with open(self.pid_file, "w") as f:
            f.write(str(pid))
        logger.info("PID file created", pid=pid, path=str(self.pid_file))

    def remove_pid(self):
        """Remove PID file."""
        self.pid_file.unlink(missing_ok=True)
        logger.info("PID file removed", path=str(self.pid_file))

    def start(self):
        """Start the daemon."""
        # Check if already running
        existing_pid = self.get_pid()
        if existing_pid:
            print(f"❌ Daemon already running with PID {existing_pid}")
            print(f"   Use './start_fullon.py stop' to stop it first")
            return 1

        print(f"🚀 Starting {DAEMON_NAME} daemon...")
        logger.info("Starting daemon", name=DAEMON_NAME)

        # Fork process
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process - write PID and exit
                self.write_pid(pid)
                print(f"✅ Daemon started with PID {pid}")
                print(f"   Log file: {self.log_file}")
                print(f"   PID file: {self.pid_file}")
                print(f"\n   Check status: ./start_fullon.py status")
                print(f"   View logs:    ./start_fullon.py logs")
                return 0

        except OSError as e:
            logger.error("Fork failed", error=str(e))
            print(f"❌ Failed to start daemon: {e}")
            return 1

        # Child process continues here
        self._run_daemon()

    def _run_daemon(self):
        """Run the daemon process (called in child after fork)."""
        # Detach from parent environment
        os.setsid()
        os.umask(0)

        # Redirect stdout/stderr to log file
        sys.stdout.flush()
        sys.stderr.flush()

        log_fd = os.open(str(self.log_file), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(log_fd, sys.stdout.fileno())
        os.dup2(log_fd, sys.stderr.fileno())

        logger.info("Daemon process started", pid=os.getpid())

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Start uvicorn server
        try:
            import uvicorn
            from fullon_master_api.main import app

            logger.info(
                "Starting uvicorn server",
                host=settings.host,
                port=settings.port,
            )

            # Run uvicorn in daemon mode
            uvicorn.run(
                app,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower(),
                reload=False,  # No reload in daemon mode
            )

        except Exception as e:
            logger.error("Daemon crashed", error=str(e), exc_info=True)
            sys.exit(1)

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal."""
        logger.info("Received SIGTERM, shutting down gracefully")
        self.remove_pid()
        sys.exit(0)

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT signal."""
        logger.info("Received SIGINT, shutting down gracefully")
        self.remove_pid()
        sys.exit(0)

    def stop(self):
        """Stop the daemon."""
        pid = self.get_pid()

        if not pid:
            print(f"❌ Daemon is not running")
            return 1

        print(f"⏹️  Stopping {DAEMON_NAME} daemon (PID {pid})...")
        logger.info("Stopping daemon", pid=pid)

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for process to stop (max 10 seconds)
            for i in range(10):
                try:
                    os.kill(pid, 0)  # Check if still running
                    time.sleep(1)
                    print(".", end="", flush=True)
                except ProcessLookupError:
                    # Process has stopped
                    break

            print()

            # Check if still running
            try:
                os.kill(pid, 0)
                # Still running, force kill
                print(f"⚠️  Daemon didn't stop gracefully, force killing...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            except ProcessLookupError:
                pass

            self.remove_pid()
            print(f"✅ Daemon stopped")
            return 0

        except ProcessLookupError:
            print(f"❌ Process {pid} not found")
            self.remove_pid()
            return 1
        except PermissionError:
            print(f"❌ Permission denied to kill process {pid}")
            return 1

    def restart(self):
        """Restart the daemon."""
        print(f"🔄 Restarting {DAEMON_NAME} daemon...")
        self.stop()
        time.sleep(2)
        return self.start()

    def status(self):
        """Show daemon status."""
        pid = self.get_pid()

        print(f"\n{'='*60}")
        print(f"{DAEMON_NAME} Daemon Status")
        print(f"{'='*60}")

        if pid:
            print(f"Status:   ✅ Running")
            print(f"PID:      {pid}")
            print(f"PID File: {self.pid_file}")
            print(f"Log File: {self.log_file}")
            print(f"\nServer:   http://{settings.host}:{settings.port}")
            print(f"Docs:     http://{settings.host}:{settings.port}/docs")
            print(f"Health:   http://{settings.host}:{settings.port}/health")
        else:
            print(f"Status:   ❌ Not running")
            print(f"PID File: {self.pid_file} (not found)")

        print(f"{'='*60}\n")

        return 0 if pid else 1

    def logs(self, follow: bool = True, lines: int = 50):
        """Show daemon logs."""
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return 1

        print(f"📋 Daemon logs: {self.log_file}")
        print(f"{'='*60}\n")

        if follow:
            # Tail -f equivalent
            import subprocess

            subprocess.run(["tail", "-f", "-n", str(lines), str(self.log_file)])
        else:
            # Show last N lines
            with open(self.log_file, "r") as f:
                lines_list = f.readlines()
                for line in lines_list[-lines:]:
                    print(line, end="")

        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} - Fullon Master API Daemon Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./start_fullon.py start          # Start the daemon
  ./start_fullon.py stop           # Stop the daemon
  ./start_fullon.py restart        # Restart the daemon
  ./start_fullon.py status         # Check status
  ./start_fullon.py logs           # Tail logs
  ./start_fullon.py logs --no-follow  # Show last 50 lines
        """,
    )

    parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "status", "logs"],
        help="Action to perform",
    )

    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Don't follow logs (only for 'logs' action)",
    )

    parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Number of log lines to show (default: 50)",
    )

    args = parser.parse_args()

    # Create daemon manager
    daemon = DaemonManager(PID_FILE, LOG_FILE)

    # Execute action
    if args.action == "start":
        return daemon.start()
    elif args.action == "stop":
        return daemon.stop()
    elif args.action == "restart":
        return daemon.restart()
    elif args.action == "status":
        return daemon.status()
    elif args.action == "logs":
        return daemon.logs(follow=not args.no_follow, lines=args.lines)


if __name__ == "__main__":
    sys.exit(main())
