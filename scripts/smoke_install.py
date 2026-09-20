"""Check the installed package and console command from an unrelated directory."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    executable = shutil.which("jev-demo")
    if not executable:
        raise RuntimeError("Installed jev-demo console command was not found")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory() as work:
        env = os.environ.copy()
        # Keep the smoke check offline and independent of the runner's credentials.
        for name in list(env):
            if name.startswith(("JEV_", "TYPESAFE_", "OPENCODE_", "PYTHONPATH")):
                env.pop(name)
        env["PATH"] = ""
        env["XDG_DATA_HOME"] = work
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        subprocess.run(
            [executable, "--help"], cwd=work, env=env, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15, **flags,
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-m", "jev_demo", "--port", str(port)], cwd=work, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **flags,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode(errors="replace"))
                try:
                    with urlopen(base, timeout=1) as response:
                        page = response.read().decode()
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("The installed app did not start")
            assert "Ask Jev" in page
            with urlopen(base + "/static/index.html", timeout=5) as response:
                assert "Ask Jev" in response.read().decode()
            request = Request(base + "/api/decide", data=json.dumps({
                "recipe": "ticket", "text": "Please refund my duplicate payment.", "mock": True,
            }).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
            assert result["mode"] == "mock"
            assert result["policy"]["action"] == "billing-refund"
            print("Installed CLI, bundled page, and mock API work outside the source directory.")
        finally:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    main()
