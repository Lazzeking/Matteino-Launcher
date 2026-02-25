# workers/mod_search_worker.py
"""
Background worker to search mods on Modrinth and/or CurseForge.
Emits (list of hit dicts, total_count). Pagination: 20 results per page.
"""

import json
import requests
from PyQt6.QtCore import QObject, pyqtSignal

MODRINTH_API = "https://api.modrinth.com/v2"
CURSEFORGE_API_BASE = "https://api.curseforge.com/v1"
GAME_ID = 432  # Minecraft
PAGE_SIZE = 20


class ModSearchWorker(QObject):
    finished = pyqtSignal(int, list, int)  # (page, hits, total_count)
    error = pyqtSignal(str)

    def __init__(self, query: str, provider: str, page: int = 0, game_version: str = "", loader: str = "", curseforge_api_key: str = "", parent=None):
        super().__init__(parent)
        self.query = (query or "").strip()
        self.provider = provider  # "modrinth", "curseforge", or "both"
        self.page = max(0, int(page))
        self.game_version = (game_version or "").strip()
        self.loader = (loader or "").strip()
        self.curseforge_api_key = (curseforge_api_key or "").strip()

    def run(self):
        if not self.query:
            self.finished.emit(self.page, [], 0)
            return

        all_hits = []
        total = 0

        if self.provider in ("modrinth", "both"):
            try:
                hits, tot = self._search_modrinth()
                all_hits.extend(hits)
                total += tot
            except Exception as e:
                self.error.emit(f"Modrinth: {e}")

        if self.provider in ("curseforge", "both"):
            if not self.curseforge_api_key:
                self.error.emit("CurseForge API key not set; skip CurseForge or set curseforge_api_key.")
            else:
                try:
                    hits, tot = self._search_curseforge()
                    all_hits.extend(hits)
                    total += tot
                except Exception as e:
                    self.error.emit(f"CurseForge: {e}")

        # Re-sort by relevance to query so e.g. "Brutal bosses" appears at top when API order is poor
        all_hits = self._sort_hits_by_relevance(all_hits, self.query)
        self.finished.emit(self.page, all_hits, total)

    def _search_modrinth(self):
        facets = [["project_type:mod"]]
        if self.game_version:
            facets.append([f"versions:{self.game_version}"])
        if self.loader:
            facets.append([f"categories:{self.loader}"])

        limit = PAGE_SIZE if self.provider == "modrinth" else (PAGE_SIZE // 2)
        offset = self.page * limit

        # Explicit relevance sort so "Brutal bosses" etc. appear by best match to query
        params = {
            "query": self.query,
            "limit": limit,
            "offset": offset,
            "index": "relevance",
        }
        if facets:
            params["facets"] = json.dumps(facets)

        r = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        total_hits = data.get("total_hits", 0)

        out = []
        for h in hits:
            slug = h.get("slug", "")
            project_id = h.get("project_id", "")
            out.append({
                "provider": "modrinth",
                "slug": slug,
                "project_id": project_id,
                "title": h.get("title", slug),
                "description": (h.get("description") or "")[:200],
                "icon_url": h.get("icon_url") or "",
                "url": f"https://modrinth.com/mod/{slug}",
            })
        return out, total_hits

    def _search_curseforge(self):
        headers = {"x-api-key": self.curseforge_api_key, "Accept": "application/json"}
        limit = PAGE_SIZE if self.provider == "curseforge" else (PAGE_SIZE // 2)
        index = self.page * limit
        # sortField: 0=Featured, 1=Popularity, 2=LastUpdate, 3=Name, 5=TotalDownloads. Omit for API default (often relevance when searchFilter is set).
        # Narrow by gameVersion when set so results match the pack and relevance can be better.
        params = {
            "gameId": GAME_ID,
            "searchFilter": self.query,
            "index": index,
            "pageSize": limit,
        }
        if self.game_version:
            params["gameVersion"] = self.game_version
        r = requests.get(f"{CURSEFORGE_API_BASE}/mods/search", headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        mods = data.get("data", [])
        pagination = data.get("pagination", {})
        total_count = pagination.get("totalCount", len(mods) + index)

        out = []
        for m in mods:
            slug = m.get("slug", "")
            project_id = str(m.get("id", ""))
            out.append({
                "provider": "curseforge",
                "slug": slug,
                "project_id": project_id,
                "title": m.get("name", slug),
                "description": (m.get("summary") or "")[:200],
                "icon_url": (m.get("logo", {}) or {}).get("url") or "",
                "url": f"https://www.curseforge.com/minecraft/mc-mods/{slug}",
            })
        return out, total_count

    def _sort_hits_by_relevance(self, hits: list, query: str) -> list:
        """Sort hits so best title match to query comes first (exact/prefix > contains > rest)."""
        if not query or not hits:
            return hits
        q = query.lower().strip()

        def score(h):
            title = (h.get("title") or "").lower()
            if title == q:
                return 0
            if title.startswith(q):
                return 1
            if q in title:
                return 2
            # words in query appear in title
            q_words = [w for w in q.split() if len(w) > 1]
            if q_words and all(w in title for w in q_words):
                return 3
            return 4

        return sorted(hits, key=score)
