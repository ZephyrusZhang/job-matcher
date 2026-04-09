"""Import crawled job data from tmp/ JSON files into the database.

Usage:
    uv run python scripts/import_data.py <company_id> <json_file>

Examples:
    uv run python scripts/import_data.py bytedance ../tmp/bytedance.json
    uv run python scripts/import_data.py tencent ../tmp/tencent_jobs.json
"""
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite
from tqdm import tqdm

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import load_config
from app.crawl.category import prebatch_classify
from app.crawl.pipeline import normalize_job
from app.database import init_database

# Track source_urls within a single import run
_seen_urls: dict[str, bool] = {}


async def import_file(db: aiosqlite.Connection, file_path: Path, company_id: str) -> None:
    """Import jobs from a JSON file."""
    with open(file_path) as f:
        data = json.load(f)

    raw_jobs = data if isinstance(data, list) else data.get("jobs", [])
    inserted = 0
    skipped_non_tech = 0
    skipped_duplicate = 0
    skipped_existing = 0

    print(f"\n📂 {file_path.name} → {company_id}  (共 {len(raw_jobs)} 条)")

    # Pre-batch LLM classification (32 jobs per request)
    print("⏳ 正在批量调用 LLM 归一化 category...")
    llm_pbar = tqdm(total=0, desc="LLM 分类", unit="item", ncols=100)

    def llm_progress(done: int, total: int):
        if llm_pbar.total != total:
            llm_pbar.total = total
        llm_pbar.n = done
        llm_pbar.refresh()

    generic_cache = prebatch_classify(raw_jobs, batch_size=32, progress_callback=llm_progress)
    llm_pbar.close()
    print(f"✅ LLM 分类完成 (generic_cache: {len(generic_cache)} 条)")

    pbar = tqdm(
        raw_jobs,
        desc="导入中",
        unit="job",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {postfix}]",
    )

    def update_postfix():
        pbar.set_postfix_str(
            f"新增={inserted} 已存在={skipped_existing} "
            f"重复={skipped_duplicate} 非技术={skipped_non_tech}"
        )

    for raw_job in pbar:
        job = normalize_job(raw_job, company_id, generic_cache=generic_cache)

        # Non-tech job (LLM explicitly classified as null)
        if not job["category"]:
            skipped_non_tech += 1
            tqdm.write(f"  [非技术岗] {job['title']}  {raw_job.get('source_url', '')}")
            update_postfix()
            continue

        source_url = job.get("source_url", "")

        # Check if source_url already exists in DB (same company + same page = same job)
        if source_url:
            async with db.execute(
                "SELECT id, title FROM jobs WHERE source_url = ? AND company_id = ?",
                (source_url, company_id),
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    skipped_existing += 1
                    update_postfix()
                    continue

        # Check if source_url already seen in this batch
        if source_url and source_url in _seen_urls:
            skipped_duplicate += 1
            tqdm.write(f"  [文件内重复] {job['title']}  {source_url}")
            update_postfix()
            continue
        if source_url:
            _seen_urls[source_url] = True

        await db.execute(
            """
            INSERT INTO jobs (id, company_id, title, category, location, job_type,
                             responsibilities, requirements_must, requirements_nice,
                             department, department_product, education, experience,
                             posted_date, source_url, summary, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"], job["company_id"], job["title"], job["category"],
                json.dumps(job["location"], ensure_ascii=False),
                job["job_type"], job["responsibilities"],
                json.dumps(job["requirements_must"], ensure_ascii=False),
                json.dumps(job["requirements_nice"], ensure_ascii=False),
                job["department"], job["department_product"],
                job["education"], job["experience"],
                job["posted_date"], job["source_url"],
                job["summary"], job["content_hash"],
            ),
        )
        inserted += 1
        update_postfix()

    pbar.close()
    await db.commit()

    print(f"\n📊 完成: 总数 {len(raw_jobs)} | 新增 {inserted} | "
          f"已存在 {skipped_existing} | 文件内重复 {skipped_duplicate} | "
          f"非技术 {skipped_non_tech}")


async def main():
    if len(sys.argv) < 3:
        print("Usage: uv run python scripts/import_data.py <company_id> <json_file>")
        print("Example: uv run python scripts/import_data.py bytedance ../tmp/bytedance.json")
        sys.exit(1)

    company_id = sys.argv[1]
    file_path = Path(sys.argv[2])

    # Resolve relative path from cwd
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    file_path = file_path.resolve()

    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        sys.exit(1)

    config = load_config(str(backend_dir / "config"))
    if not Path(config.database.path).is_absolute():
        config.database.path = str(backend_dir / config.database.path)

    await init_database(config.database)

    db = await aiosqlite.connect(config.database.path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")

    _seen_urls.clear()
    await import_file(db, file_path, company_id)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
