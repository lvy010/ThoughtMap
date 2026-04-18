#!/usr/bin/env python3
"""Enrich github_repos_cn.md: match README articles to fork projects, sort by date, normalize labels."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
CN_MD = REPO_ROOT / "repo" / "github_repos_cn.md"

TAG_TO_PROJECT: dict[str, str] = {
    "nano-vllm": "nano-vllm",
    "manim": "manim",
    "mlflow": "mlflow",
    "liveportrait": "LivePortrait",
    "sora": "Open-Sora-Plan",
    "open-sora-plan": "Open-Sora-Plan",
    "ai tradingos": "nofx",
    "robotics_py": "PythonRobotics",
    "cuda": "cuda-training",
    "cpprestsdk": "cpprestsdk",
    "py-spy": "py-spy",
    "comfyui": "ComfyUI",
    "audacity": "audacity",
    "llamafactory": "LlamaFactory",
    "qwen3.5": "Qwen3.5",
    "pilot智驾系统": "FrogPilot",
    "pilot智驾": "FrogPilot",
    "vroom": "FrogPilot",
    "llama.cpp": "llama.cpp",
    "stable-diffusion.cpp": "stable-diffusion.cpp",
    "mcp-servers": "awesome-mcp-servers",
    "carbonyl": "carbonyl",
    "searxng": "searxng",
    "neovim": "neovim",
    "godot": "godot",
    "flutter": "flutter",
    "micropython": "micropython",
    "strongswan": "strongswan",
    "perfetto": "perfetto",
    "tracy": "tracy",
    "ladybird": "ladybird",
    "serenity": "serenity",
    "leveldb": "leveldb",
    "rocksdb": "rocksdb",
    "vite": "vite",
    "shiki": "shiki",
    "bevy": "bevy",
    "tantivy": "tantivy",
    "makepad": "makepad",
    "arroyo": "arroyo",
    "triton": "triton",
    "chatdev": "ChatDev",
    "megatts3": "MegaTTS3",
    "megengine": "MegEngine",
    "openvela": "packages_demos",
    "slidev": "slidev",
    "firecrawl": "firecrawl",
    "openmanus": "OpenManus",
    "agentscope": "agentscope",
    "fastmcp": "fastmcp",
    "vid-llm": "Director",
    "rengine": "rengine",
    "kubernetes-the-hard-way": "kubernetes-the-hard-way",
    "social-analyzer": "social-analyzer",
    "trape": "trape",
    "nebula": "nebula",
    "abseil-cpp": "abseil-cpp",
    "crow": "Crow",
    "drogon": "drogon",
    "cpp-httplib": "cpp-httplib",
    "testlib": "testlib",
    "arduino-foc": "Arduino-FOC",
    "visp": "visp",
    "box64": "box64",
    "opentitan": "opentitan",
    "chromium": "chromium",
    "postgres": "postgres",
    "sqlite": "sqlite",
    "git": "git",
    "coflux": "Coflux",
    "cello": "Cello",
    "qlib": "daily_stock_analysis",
    "sim-ai_vid": "Director",
    "sync_ai_vid": "Director",
    "xiaozhi-esp32": "packages_demos",
}


def extract_articles_from_readme(readme_text: str) -> list[tuple[str, str, str]]:
    """Extract (tag, title, url) from README article links like `- [\\[tag\\] title](url)`."""
    pattern = re.compile(
        r"^- \[(?:\\?\[)([^\]\\]+?)(?:\\?\])\s*(.*?)\]\((https?://[^\)]+)\)",
        re.MULTILINE,
    )
    results: list[tuple[str, str, str]] = []
    for m in pattern.finditer(readme_text):
        tag = m.group(1).strip()
        rest = m.group(2).strip()
        url = m.group(3).strip()
        full_title = f"[{tag}] {rest}" if rest else f"[{tag}]"
        results.append((tag, full_title, url))
    return results


def build_project_articles(
    articles: list[tuple[str, str, str]], fork_names: set[str]
) -> dict[str, list[tuple[str, str]]]:
    """Map articles to fork project names. Returns {project_name: [(title, url), ...]}."""
    fork_lower = {n.lower(): n for n in fork_names}
    mapping: dict[str, list[tuple[str, str]]] = {}

    for tag, title, url in articles:
        tag_lower = tag.lower().strip()
        project = None

        if tag_lower in TAG_TO_PROJECT:
            project = TAG_TO_PROJECT[tag_lower]
        elif tag_lower in fork_lower:
            project = fork_lower[tag_lower]
        else:
            for fl, fn in fork_lower.items():
                if tag_lower == fl or fl.startswith(tag_lower) or tag_lower.startswith(fl):
                    project = fn
                    break

        if project and project in fork_names:
            mapping.setdefault(project, [])
            if (title, url) not in mapping[project]:
                mapping[project].append((title, url))

    return mapping


def parse_fork_sections(fork_text: str) -> list[tuple[str, str, list[dict]]]:
    """Parse fork sections into [(section_header, section_quote, [project_dicts])]."""
    section_pat = re.compile(r"^### (.+)$", re.MULTILINE)
    splits = list(section_pat.finditer(fork_text))

    sections: list[tuple[str, str, list[dict]]] = []
    for i, match in enumerate(splits):
        header = match.group(1)
        start = match.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(fork_text)
        body = fork_text[start:end]

        quote = ""
        quote_m = re.match(r"\s*\n(> .+)\n", body)
        if quote_m:
            quote = quote_m.group(1)

        projects = parse_projects_in_section(body)
        sections.append((header, quote, projects))

    return sections


def parse_projects_in_section(body: str) -> list[dict]:
    """Parse numbered project entries from a section body."""
    proj_pat = re.compile(
        r"^\d+\.\s+\[([^\]]+)\]\(([^\)]+)\)(.*?)\n"
        r"((?:\s+- .+\n)*)",
        re.MULTILINE,
    )
    projects: list[dict] = []
    for m in proj_pat.finditer(body):
        name = m.group(1)
        url = m.group(2)
        suffix = m.group(3).strip()
        detail_block = m.group(4)

        lang = ""
        lang_m = re.search(r"`(\w[^`]*)`", suffix)
        if lang_m:
            lang = lang_m.group(1)

        desc = ""
        date = ""
        for line in detail_block.strip().split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line.startswith("Last Modified:") or line.startswith("LM:"):
                date = line.split(":", 1)[1].strip()
            elif line.startswith("最后更新："):
                date = line.replace("最后更新：", "").strip()
            elif line:
                desc = line

        projects.append({
            "name": name,
            "url": url,
            "lang": lang,
            "desc": desc,
            "date": date,
        })

    return projects


def rebuild_fork_sections(
    sections: list[tuple[str, str, list[dict]]],
    article_map: dict[str, list[tuple[str, str]]],
) -> str:
    """Rebuild fork markdown with sorted projects and linked articles."""
    lines: list[str] = []

    for header, quote, projects in sections:
        projects.sort(key=lambda p: p["date"], reverse=True)

        lines.append(f"### {header}")
        lines.append("")
        if quote:
            lines.append(quote)
            lines.append("")

        for i, p in enumerate(projects, 1):
            lang_tag = f" `{p['lang']}`" if p["lang"] else ""
            lines.append(f"{i}. [{p['name']}]({p['url']}){lang_tag}")
            if p["desc"]:
                lines.append(f"   - {p['desc']}")
            lines.append(f"   - LM: {p['date']}")

            arts = article_map.get(p["name"], [])
            if arts:
                lines.append(f"   - 相关文章：")
                for title, url in arts:
                    lines.append(f"     - [{title}]({url})")

            lines.append("")

    return "\n".join(lines)


def main() -> None:
    readme_text = README.read_text(encoding="utf-8")
    cn_text = CN_MD.read_text(encoding="utf-8")

    marker = "## Fork 项目（210 个）— 按方向分类"
    before_fork, fork_and_after = cn_text.split(marker, 1)

    stats_marker = "---\n\n## 统计"
    if stats_marker in fork_and_after:
        fork_body, stats_part = fork_and_after.split(stats_marker, 1)
        stats_part = "---\n\n## 统计" + stats_part
    else:
        fork_body = fork_and_after
        stats_part = ""

    before_fork = before_fork.replace("最后更新：", "LM: ").replace("Last Modified: ", "LM: ")

    sections = parse_fork_sections(fork_body)

    all_fork_names: set[str] = set()
    for _, _, projects in sections:
        for p in projects:
            all_fork_names.add(p["name"])

    articles = extract_articles_from_readme(readme_text)
    print(f"Extracted {len(articles)} tagged articles from README.md")

    article_map = build_project_articles(articles, all_fork_names)
    matched_count = sum(len(v) for v in article_map.values())
    print(f"Matched {matched_count} articles to {len(article_map)} fork projects")
    for proj, arts in sorted(article_map.items(), key=lambda x: -len(x[1])):
        print(f"  {proj}: {len(arts)} articles")

    new_fork = rebuild_fork_sections(sections, article_map)

    stats_part = stats_part.replace("最后更新：", "LM: ").replace("Last Modified: ", "LM: ")

    result = before_fork + marker + "\n\n" + new_fork + stats_part
    CN_MD.write_text(result, encoding="utf-8")
    print(f"\nUpdated {CN_MD}")


if __name__ == "__main__":
    main()
