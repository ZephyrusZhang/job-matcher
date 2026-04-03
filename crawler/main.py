import json
import sys
from datetime import datetime
from pathlib import Path

from src.agent import AgentRunner
from src.handlers import ConsoleHandler, FileHandler


def main():
    if len(sys.argv) < 2:
        print("用法: uv run python main.py <招聘网站URL>")
        print("示例: uv run python main.py 'https://join.qq.com/post.html'")
        sys.exit(1)

    url = sys.argv[1]
    runner = AgentRunner(handlers=[
        ConsoleHandler(verbose=True),
        FileHandler(log_dir="logs"),
    ])
    jobs = runner.run(f"爬取该招聘网站的所有岗位信息：{url}")

    if not jobs:
        print("\n未获取到任何岗位数据。")
        sys.exit(1)

    # 保存到 tmp/ 目录
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"jobs_{ts}.json"
    out_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n爬取完成，共 {len(jobs)} 条岗位数据，已保存到 {out_path}")


if __name__ == "__main__":
    main()
