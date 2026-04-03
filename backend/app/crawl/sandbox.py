import io
import os
import tarfile
import threading

import docker


SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "crawler-sandbox")
SANDBOX_WORKDIR = "/home/user"


class SandboxManager:
    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None

    def ensure_sandbox(self):
        if self.container is not None:
            return
        self.client = docker.from_env()
        self.container = self.client.containers.run(
            SANDBOX_IMAGE,
            command="sleep infinity",
            working_dir=SANDBOX_WORKDIR,
            detach=True,
            remove=True,
            mem_limit="1g",
            cpu_period=100000,
            cpu_quota=100000,
        )

    def write_file(self, path: str, content: str) -> dict:
        self.ensure_sandbox()
        data = content.encode("utf-8")
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tar:
            info = tarfile.TarInfo(name=os.path.basename(path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)
        dest_dir = os.path.dirname(path) or SANDBOX_WORKDIR
        self.container.put_archive(dest_dir, tar_buf)
        return {"status": "ok", "path": path, "size": len(data)}

    def run_command(self, command: str, timeout: int = 120) -> dict:
        self.ensure_sandbox()

        result = {"exit_code": -1, "stdout": "", "stderr": ""}
        exception = [None]

        def _exec():
            try:
                exit_code, output = self.container.exec_run(
                    ["bash", "-c", command],
                    workdir=SANDBOX_WORKDIR,
                    demux=True,
                )
                result["exit_code"] = exit_code
                stdout = (output[0] or b"").decode("utf-8", errors="replace")
                stderr = (output[1] or b"").decode("utf-8", errors="replace")
                result["stdout"] = stdout[-5000:] if len(stdout) > 5000 else stdout
                result["stderr"] = stderr[-3000:] if len(stderr) > 3000 else stderr
            except Exception as e:
                exception[0] = e

        t = threading.Thread(target=_exec)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            return {"exit_code": -1, "stdout": "", "stderr": f"命令超时（{timeout}s）"}

        if exception[0]:
            raise exception[0]

        return result

    def read_file(self, path: str) -> str:
        self.ensure_sandbox()
        bits, _ = self.container.get_archive(path)
        buf = io.BytesIO()
        for chunk in bits:
            buf.write(chunk)
        buf.seek(0)
        with tarfile.open(fileobj=buf) as tar:
            member = tar.getmembers()[0]
            f = tar.extractfile(member)
            return f.read().decode("utf-8")

    def kill(self):
        if self.container:
            try:
                self.container.stop(timeout=5)
            except Exception:
                pass
            self.container = None
        self.client = None
