#!/usr/bin/env python3
"""Fetch all GitHub repositories for a user and generate a structured index."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests
from requests import Session
from requests.adapters import HTTPAdapter, Retry

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "repo"
OUTPUT_MD = OUTPUT_DIR / "github_repos.md"
OUTPUT_CN_MD = OUTPUT_DIR / "github_repos_cn.md"
OUTPUT_CSV = OUTPUT_DIR / "github_repos.csv"

USERNAME = "lvy010"
API_BASE = "https://api.github.com"
PER_PAGE = 100
REQUEST_TIMEOUT = 30

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


@dataclass
class RepoInfo:
    name: str
    url: str
    description: str
    stars: int
    forks: int
    language: str
    fork: bool
    updated_at: str
    created_at: str
    topics: List[str]
    license: str

    @property
    def origin_tag(self) -> str:
        return "Fork" if self.fork else "Original"

    @property
    def update_date(self) -> str:
        return self.updated_at[:10] if self.updated_at else "N/A"

    @property
    def create_date(self) -> str:
        return self.created_at[:10] if self.created_at else "N/A"


def build_session(token: Optional[str] = None) -> Session:
    session = requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)
    retry = Retry(
        total=5,
        read=3,
        connect=3,
        backoff_factor=1.0,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_all_repos(session: Session) -> List[RepoInfo]:
    """Paginate through the GitHub API to collect every public repo."""
    repos: List[RepoInfo] = []
    page = 1
    while True:
        url = f"{API_BASE}/users/{USERNAME}/repos"
        params = {
            "per_page": PER_PAGE,
            "page": page,
            "type": "all",
            "sort": "updated",
            "direction": "desc",
        }
        print(f"  Fetching page {page} ...", file=sys.stderr)
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        remaining = resp.headers.get("X-RateLimit-Remaining", "?")
        print(f"  Rate limit remaining: {remaining}", file=sys.stderr)

        data = resp.json()
        if not data:
            break

        for raw in data:
            license_name = ""
            if raw.get("license") and raw["license"].get("spdx_id"):
                license_name = raw["license"]["spdx_id"]

            repos.append(
                RepoInfo(
                    name=raw["name"],
                    url=raw["html_url"],
                    description=raw.get("description") or "",
                    stars=raw.get("stargazers_count", 0),
                    forks=raw.get("forks_count", 0),
                    language=raw.get("language") or "",
                    fork=raw.get("fork", False),
                    updated_at=raw.get("pushed_at") or raw.get("updated_at", ""),
                    created_at=raw.get("created_at", ""),
                    topics=raw.get("topics", []),
                    license=license_name,
                )
            )

        if len(data) < PER_PAGE:
            break
        page += 1
        time.sleep(0.3)

    return repos


def build_markdown(repos: List[RepoInfo]) -> str:
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    originals = [r for r in repos if not r.fork]
    forks = [r for r in repos if r.fork]

    originals.sort(key=lambda r: r.stars, reverse=True)
    forks.sort(key=lambda r: r.stars, reverse=True)

    lines: List[str] = []
    lines.append(f"# GitHub Repos Index — {USERNAME}")
    lines.append("")
    lines.append(f"> Generated: {generated_at}")
    lines.append(f"> Total repositories: **{len(repos)}** "
                 f"(Original: {len(originals)}, Forked: {len(forks)})")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Table of Contents")
    lines.append("")
    lines.append(f"- [Original Projects ({len(originals)})](#original-projects)")
    lines.append(f"- [Forked Projects ({len(forks)})](#forked-projects)")
    lines.append(f"- [Statistics](#statistics)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Original Projects")
    lines.append("")
    lines.append("| # | Project | Description | ⭐ | Language | Updated |")
    lines.append("|---|---------|-------------|----|----------|---------|")
    for i, r in enumerate(originals, 1):
        desc = r.description.replace("|", "\\|")[:120]
        lines.append(
            f"| {i} | [{r.name}]({r.url}) | {desc} "
            f"| {r.stars} | {r.language} | {r.update_date} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Forked Projects")
    lines.append("")
    lines.append("| # | Project | Description | ⭐ | Language | Updated |")
    lines.append("|---|---------|-------------|----|----------|---------|")
    for i, r in enumerate(forks, 1):
        desc = r.description.replace("|", "\\|")[:120]
        lines.append(
            f"| {i} | [{r.name}]({r.url}) | {desc} "
            f"| {r.stars} | {r.language} | {r.update_date} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")

    lang_count: dict[str, int] = {}
    for r in repos:
        lang = r.language or "Unknown"
        lang_count[lang] = lang_count.get(lang, 0) + 1
    sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)

    lines.append("### Language Distribution")
    lines.append("")
    lines.append("| Language | Count |")
    lines.append("|----------|-------|")
    for lang, count in sorted_langs:
        lines.append(f"| {lang} | {count} |")
    lines.append("")

    total_stars = sum(r.stars for r in repos)
    total_forks = sum(r.forks for r in repos)
    lines.append(f"### Overview")
    lines.append("")
    lines.append(f"- Total Stars: **{total_stars}**")
    lines.append(f"- Total Forks: **{total_forks}**")
    lines.append(f"- Most used language: **{sorted_langs[0][0]}** ({sorted_langs[0][1]} repos)")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_chinese_markdown(repos: List[RepoInfo]) -> str:
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    originals = [r for r in repos if not r.fork]
    forks = [r for r in repos if r.fork]

    originals.sort(key=lambda r: r.stars, reverse=True)
    forks.sort(key=lambda r: r.stars, reverse=True)

    lines: List[str] = []
    lines.append(f"# GitHub 项目索引 — {USERNAME}")
    lines.append("")
    lines.append(f"> 生成时间：{generated_at}")
    lines.append(f"> 仓库总数：**{len(repos)}** 个"
                 f"（原创 {len(originals)} 个，Fork {len(forks)} 个）")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append(f"## 原创项目（{len(originals)} 个）")
    lines.append("")
    for i, r in enumerate(originals, 1):
        lang_tag = f" `{r.language}`" if r.language else ""
        star_tag = f" ⭐{r.stars}" if r.stars > 0 else ""
        lines.append(f"{i}. [{r.name}]({r.url}){star_tag}{lang_tag}")
        if r.description:
            lines.append(f"   - {r.description}")
        lines.append(f"   - 最后更新：{r.update_date}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"## Fork 项目（{len(forks)} 个）")
    lines.append("")
    for i, r in enumerate(forks, 1):
        lang_tag = f" `{r.language}`" if r.language else ""
        star_tag = f" ⭐{r.stars}" if r.stars > 0 else ""
        lines.append(f"{i}. [{r.name}]({r.url}){star_tag}{lang_tag}")
        if r.description:
            lines.append(f"   - {r.description}")
        lines.append(f"   - 最后更新：{r.update_date}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 统计")
    lines.append("")

    lang_count: dict[str, int] = {}
    for r in repos:
        lang = r.language or "未知"
        lang_count[lang] = lang_count.get(lang, 0) + 1
    sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)

    lines.append("### 语言分布")
    lines.append("")
    for lang, count in sorted_langs:
        lines.append(f"- **{lang}**：{count} 个")
    lines.append("")

    total_stars = sum(r.stars for r in repos)
    total_forks = sum(r.forks for r in repos)
    lines.append("### 总览")
    lines.append("")
    lines.append(f"- 总 Star 数：**{total_stars}**")
    lines.append(f"- 总 Fork 数：**{total_forks}**")
    lines.append(f"- 最常用语言：**{sorted_langs[0][0]}**（{sorted_langs[0][1]} 个仓库）")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_csv(repos: List[RepoInfo]) -> str:
    lines: List[str] = []
    lines.append("Name,URL,Description,Stars,Forks,Language,Type,Updated,Created,License")
    for r in sorted(repos, key=lambda r: r.stars, reverse=True):
        desc = r.description.replace('"', '""')
        lines.append(
            f'"{r.name}","{r.url}","{desc}",'
            f"{r.stars},{r.forks},"
            f'"{r.language}","{r.origin_tag}",'
            f'"{r.update_date}","{r.create_date}","{r.license}"'
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    import os

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print(
            "Tip: set GITHUB_TOKEN env var to raise rate limit from 60 to 5000 req/h",
            file=sys.stderr,
        )

    session = build_session(token or None)

    print(f"Fetching all repos for {USERNAME} ...", file=sys.stderr)
    repos = fetch_all_repos(session)
    print(f"Fetched {len(repos)} repositories.", file=sys.stderr)

    if not repos:
        print("No repositories found!", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    md = build_markdown(repos)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"Markdown index  -> {OUTPUT_MD}", file=sys.stderr)

    cn_md = build_chinese_markdown(repos)
    OUTPUT_CN_MD.write_text(cn_md, encoding="utf-8")
    print(f"Chinese index   -> {OUTPUT_CN_MD}", file=sys.stderr)

    csv = build_csv(repos)
    OUTPUT_CSV.write_text(csv, encoding="utf-8")
    print(f"CSV export      -> {OUTPUT_CSV}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
