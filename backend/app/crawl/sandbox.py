import io
import logging
import os
import tarfile
import threading

import docker


logger = logging.getLogger(__name__)

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "crawler-sandbox")
SANDBOX_WORKDIR = "/home/user"

# Marks every container this project starts, so cleanup never touches
# unrelated containers that happen to share the image.
SANDBOX_LABEL = "job-matcher.sandbox"

# When a crawl fails, keep its container so the generated crawler.py and any
# partial output.json can still be inspected. Successful crawls are always
# cleaned up. Set to "false" to reclaim failed containers too.
KEEP_SANDBOX_ON_FAILURE = os.getenv("KEEP_SANDBOX_ON_FAILURE", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


class SandboxManager:
    """Owns one Docker sandbox container for the lifetime of a crawl.

    Use as a context manager, or call ``cleanup(success=...)`` when the crawl
    finishes. Leaving containers behind is what caused them to pile up: each
    crawl (and each cached-script run) starts one, and nothing removed them.
    """

    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None

    def __enter__(self) -> "SandboxManager":
        """Enter a crawl scope; the container is created lazily on first use."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Clean up, treating any in-flight exception as a failed crawl."""
        self.cleanup(success=exc_type is None)

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
            labels={SANDBOX_LABEL: "1"},
        )
        logger.info(f"[sandbox] started container {self.container.short_id}")

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
        """Stop and remove the container. Safe to call more than once."""
        if self.container:
            short_id = self.container.short_id
            try:
                # Containers are created with remove=True, so stopping is
                # normally enough; force-remove covers a stop that times out.
                self.container.stop(timeout=5)
                logger.info(f"[sandbox] removed container {short_id}")
            except Exception as e:
                logger.warning(f"[sandbox] stop failed for {short_id}: {e}")
                try:
                    self.container.remove(force=True)
                    logger.info(f"[sandbox] force-removed container {short_id}")
                except Exception as e2:
                    logger.warning(f"[sandbox] force-remove failed for {short_id}: {e2}")
            self.container = None
        self.client = None

    def cleanup(self, success: bool = True) -> None:
        """Release the container once a crawl is done.

        Args:
            success: Whether the crawl succeeded. Failed crawls keep their
                container when ``KEEP_SANDBOX_ON_FAILURE`` is set, so the
                generated script and partial output stay inspectable.
        """
        if self.container is None:
            return

        if not success and KEEP_SANDBOX_ON_FAILURE:
            logger.info(
                f"[sandbox] keeping container {self.container.short_id} for debugging "
                f"(crawl failed; set KEEP_SANDBOX_ON_FAILURE=false to reclaim)"
            )
            self.container = None
            self.client = None
            return

        self.kill()

    @staticmethod
    def reap_stale(older_than_seconds: int = 0) -> int:
        """Remove sandbox containers left over from previous runs.

        A crashed or force-killed backend never gets to clean up, so its
        containers linger indefinitely. Called at startup, where none of this
        process's own containers exist yet.

        Args:
            older_than_seconds: Only remove containers older than this. ``0``
                removes every sandbox container found.

        Returns:
            How many containers were removed.
        """
        import datetime

        try:
            client = docker.from_env()
        except Exception as e:
            logger.warning(f"[sandbox] reap skipped, docker unavailable: {e}")
            return 0

        removed = 0
        try:
            # Match both labelled containers and any predating the label.
            candidates = {
                c.id: c
                for c in client.containers.list(all=True, filters={"label": SANDBOX_LABEL})
                + client.containers.list(all=True, filters={"ancestor": SANDBOX_IMAGE})
            }
            for container in candidates.values():
                if older_than_seconds > 0:
                    created = container.attrs.get("Created", "")
                    try:
                        started = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age = (datetime.datetime.now(datetime.UTC) - started).total_seconds()
                        if age < older_than_seconds:
                            continue
                    except Exception:
                        pass
                try:
                    container.remove(force=True)
                    removed += 1
                except Exception as e:
                    logger.warning(f"[sandbox] reap failed for {container.short_id}: {e}")
        except Exception as e:
            logger.warning(f"[sandbox] reap failed: {e}")

        if removed:
            logger.info(f"[sandbox] reaped {removed} stale container(s)")
        return removed
