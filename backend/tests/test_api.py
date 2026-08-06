import pytest


@pytest.mark.asyncio
async def test_companies(client):
    resp = await client.get("/api/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 3
    names = {c["name"] for c in data["data"]}
    assert "字节跳动" in names


@pytest.mark.asyncio
async def test_jobs_list(client):
    resp = await client.get("/api/jobs", params={"company_id": "bytedance"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_jobs_list_with_category_filter(client):
    resp = await client.get("/api/jobs", params={"company_id": "bytedance", "category": "前端"})
    data = resp.json()
    assert data["pagination"]["total"] == 1
    assert data["data"][0]["category"] == "前端"


@pytest.mark.asyncio
async def test_jobs_search(client):
    resp = await client.get("/api/jobs/search", params={"q": "前端"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_jobs_suggest(client):
    resp = await client.get("/api/jobs/suggest", params={"q": "前端"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_job_detail(client):
    resp = await client.get("/api/jobs/j1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["id"] == "j1"


@pytest.mark.asyncio
async def test_job_detail_carries_prose_as_two_plain_strings(client):
    """A posting's text is description + requirements, and nothing else.

    Pins the shape the frontend renders: both are the site's own text, so
    neither may come back as the old ``{must_have, nice_to_have}`` object, and
    none of the dropped columns may reappear.
    """
    resp = await client.get("/api/jobs/j1")
    job = resp.json()["data"]

    assert job["description"] == "前端开发"
    assert job["requirements"] == "React"

    dropped = {
        "responsibilities", "requirements_must", "requirements_nice",
        "department", "department_product", "education", "experience", "summary",
    }
    assert dropped.isdisjoint(job)


@pytest.mark.asyncio
async def test_job_not_found(client):
    resp = await client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_favorites_crud(client):
    # Add
    resp = await client.post("/api/favorites", json={"job_id": "j1"})
    assert resp.status_code == 201
    assert resp.json()["data"]["job_id"] == "j1"

    # List
    resp = await client.get("/api/favorites")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # Summary
    resp = await client.get("/api/favorites/summary")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["count"] == 1

    # Remove
    resp = await client.delete("/api/favorites/j1")
    assert resp.status_code == 200

    # Verify removed
    resp = await client.get("/api/favorites")
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_favorite_nonexistent_job(client):
    resp = await client.post("/api/favorites", json={"job_id": "nonexistent"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clear_company_jobs(client):
    """Clearing empties one company and takes its favourites with it."""
    await client.post("/api/favorites", json={"job_id": "j1"})

    resp = await client.delete("/api/companies/bytedance/jobs")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"deleted_jobs": 2, "deleted_favorites": 1}

    # Gone, and the favourite went by cascade rather than being left dangling.
    assert (await client.get("/api/jobs?company_id=bytedance")).json()["pagination"]["total"] == 0
    assert (await client.get("/api/favorites")).json()["data"] == []

    # Other companies are untouched, and the company row itself survives.
    assert (await client.get("/api/jobs?company_id=tencent")).json()["pagination"]["total"] == 1
    assert (await client.get("/api/jobs/j3")).status_code == 200


@pytest.mark.asyncio
async def test_clear_company_jobs_is_idempotent(client):
    await client.delete("/api/companies/bytedance/jobs")
    resp = await client.delete("/api/companies/bytedance/jobs")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted_jobs"] == 0


@pytest.mark.asyncio
async def test_clear_jobs_of_unknown_company_is_404(client):
    """Not a cheerful "0 deleted" — a typo'd id must be reported as one."""
    resp = await client.delete("/api/companies/nope/jobs")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COMPANY_NOT_FOUND"


@pytest.mark.asyncio
async def test_resume_empty(client):
    resp = await client.get("/api/resume")
    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.asyncio
async def test_settings_get(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["display_density"] == "comfortable"
    assert data["language"] == "zh"


@pytest.mark.asyncio
async def test_settings_update(client):
    resp = await client.patch("/api/settings", json={"display_density": "compact"})
    assert resp.status_code == 200
    assert resp.json()["data"]["display_density"] == "compact"


@pytest.mark.asyncio
async def test_crawl_trigger(client):
    resp = await client.post("/api/crawl/trigger", json={"company_id": "bytedance"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "pending"

    # Trigger again should fail
    resp = await client.post("/api/crawl/trigger", json={"company_id": "bytedance"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_crawl_tasks_list(client):
    # Trigger first
    await client.post("/api/crawl/trigger", json={"company_id": "tencent"})

    resp = await client.get("/api/crawl/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) >= 1
