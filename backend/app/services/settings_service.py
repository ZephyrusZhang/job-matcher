import aiosqlite


class SettingsService:
    async def get(self, db: aiosqlite.Connection) -> dict:
        async with db.execute("SELECT * FROM settings WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "display_density": row["display_density"],
                    "language": row["language"],
                }
            return {"display_density": "comfortable", "language": "zh"}

    async def update(
        self,
        db: aiosqlite.Connection,
        display_density: str | None = None,
        language: str | None = None,
    ) -> dict:
        current = await self.get(db)

        new_density = display_density or current["display_density"]
        new_language = language or current["language"]

        await db.execute(
            """INSERT OR REPLACE INTO settings (id, display_density, language)
               VALUES (1, ?, ?)""",
            (new_density, new_language),
        )
        await db.commit()
        return {"display_density": new_density, "language": new_language}
