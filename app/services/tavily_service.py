import asyncio
import os
from typing import Any
from urllib.parse import quote_plus, urlparse

from dotenv import load_dotenv
from tavily import AsyncTavilyClient

load_dotenv()


class TavilyRoadmapService:
    def __init__(self):
        api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
        self.client = AsyncTavilyClient(api_key=api_key) if api_key else None
        self._semaphore = asyncio.Semaphore(4)

    def _clean_text(self, value: Any) -> str:
        return " ".join(str(value or "").split())

    def _extract_step_text(self, step: Any) -> str:
        if isinstance(step, dict):
            return self._clean_text(step.get("text"))
        return self._clean_text(step)

    def _default_course_name(self, career: str, phase_title: str) -> str:
        default_name = f"{career} {phase_title} course"
        return self._clean_text(default_name) or "Career preparation course"

    def _build_query(self, career: str, phase: dict[str, Any], preferred_name: str) -> str:
        existing_recommendation = phase.get("course_recommendation")
        if not isinstance(existing_recommendation, dict):
            existing_recommendation = {}

        existing_query = self._clean_text(
            existing_recommendation.get("search_query") or phase.get("search_query")
        )
        if existing_query:
            return existing_query

        phase_title = self._clean_text(phase.get("title"))
        step_parts = []
        for step in (phase.get("steps") or [])[:3]:
            step_text = self._extract_step_text(step)
            if step_text:
                step_parts.append(step_text)

        query_parts = [
            career,
            phase_title,
            preferred_name,
            " ".join(step_parts),
            "online course",
        ]
        return self._clean_text(" ".join(part for part in query_parts if part))

    def _fallback_link(self, search_text: str) -> str:
        safe_query = quote_plus(self._clean_text(search_text) or "online course")
        return f"https://www.coursera.org/search?query={safe_query}"

    def _score_result(self, result: dict[str, Any], query: str) -> float:
        score = float(result.get("score") or 0)
        text = f"{result.get('title', '')} {result.get('content', '')}".lower()

        for keyword in (
            "course",
            "learn",
            "training",
            "tutorial",
            "certificate",
            "certification",
            "bootcamp",
            "specialization",
            "program",
        ):
            if keyword in text:
                score += 0.08

        for keyword in ("salary", "job description", "reddit", "quora"):
            if keyword in text:
                score -= 0.08

        for term in query.lower().split()[:6]:
            if len(term) > 3 and term in text:
                score += 0.02

        return score

    def _pick_best_result(self, results: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
        valid_results = [
            result
            for result in results
            if isinstance(result, dict) and self._clean_text(result.get("url"))
        ]
        if not valid_results:
            return None
        return max(valid_results, key=lambda item: self._score_result(item, query))

    def _domain_for(self, url: str) -> str:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    def _build_recommendation(
        self,
        career: str,
        phase: dict[str, Any],
        preferred_name: str,
        query: str,
        result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        phase_title = self._clean_text(phase.get("title"))
        link = self._clean_text((result or {}).get("url")) or self._fallback_link(
            query or preferred_name or career
        )
        source_title = self._clean_text((result or {}).get("title"))

        recommendation_name = (
            preferred_name
            or source_title
            or self._default_course_name(career, phase_title)
        )

        return {
            "name": recommendation_name,
            "link": link,
            "search_query": query,
            "source_title": source_title or recommendation_name,
            "source_domain": self._domain_for(link),
        }

    async def _search_phase_recommendation(
        self, career: str, phase: dict[str, Any]
    ) -> dict[str, Any]:
        phase_title = self._clean_text(phase.get("title"))
        existing_recommendation = phase.get("course_recommendation")
        if not isinstance(existing_recommendation, dict):
            existing_recommendation = {}

        preferred_name = self._clean_text(existing_recommendation.get("name")) or self._default_course_name(
            career, phase_title
        )
        query = self._build_query(career, phase, preferred_name)

        if not self.client:
            return self._build_recommendation(career, phase, preferred_name, query, None)

        try:
            async with self._semaphore:
                response = await self.client.search(
                    query=query,
                    topic="general",
                    search_depth="advanced",
                    max_results=5,
                    include_answer=False,
                    include_raw_content=False,
                )
            best_result = self._pick_best_result(response.get("results") or [], query)
            return self._build_recommendation(career, phase, preferred_name, query, best_result)
        except Exception as exc:
            print(f"Tavily roadmap search failed for {career} / {phase_title}: {exc}")
            return self._build_recommendation(career, phase, preferred_name, query, None)

    async def enrich_roadmaps(self, roadmaps: Any) -> Any:
        if not isinstance(roadmaps, list):
            return roadmaps

        tasks = []
        phase_refs = []

        for roadmap_index, roadmap in enumerate(roadmaps):
            if not isinstance(roadmap, dict):
                continue

            phases = roadmap.get("phases")
            if not isinstance(phases, list):
                roadmap["phases"] = []
                continue

            career = self._clean_text(roadmap.get("career")) or "Career"
            for phase_index, phase in enumerate(phases):
                if not isinstance(phase, dict):
                    phases[phase_index] = {"title": f"Phase {phase_index + 1}", "steps": []}
                    phase = phases[phase_index]

                tasks.append(self._search_phase_recommendation(career, phase))
                phase_refs.append((roadmap_index, phase_index))

        if not tasks:
            return roadmaps

        recommendations = await asyncio.gather(*tasks)

        for recommendation, (roadmap_index, phase_index) in zip(recommendations, phase_refs):
            roadmaps[roadmap_index]["phases"][phase_index]["course_recommendation"] = recommendation

        return roadmaps


tavily_roadmap_service = TavilyRoadmapService()
