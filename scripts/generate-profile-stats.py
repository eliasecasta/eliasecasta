#!/usr/bin/env python3

import html
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "eliasecasta")
DISPLAY_NAME = os.environ.get("PROFILE_DISPLAY_NAME", "Elias")
PROFILE_TOKEN = os.environ.get("PROFILE_STATS_TOKEN", "").strip()
API_ROOT = "https://api.github.com"
STATS_OUTPUT = Path("profile/github-stats.svg")
LANGS_OUTPUT = Path("profile/top-langs.svg")

# These repositories are intentionally omitted from the language card because
# their raw byte counts do not represent the technologies I primarily author:
# legacy platform/vendor dumps, upstream framework/tool mirrors, and asset-only
# repositories. They still remain included in the overall repository stats.
LANGUAGE_EXCLUDED_REPOS = {
    "fiscertificaciones",   # legacy WordPress/plugin/theme codebase
    "solidus",             # upstream framework source mirror
    "grommet",             # upstream UI library source mirror
    "free-for-dev",        # upstream resource-list mirror
    "readme-typing-svg",   # upstream README widget mirror
    "NoiseTorch",          # upstream utility source mirror
    "streetmerchant",      # upstream utility source mirror
    "umbala-assets",       # asset-only repository
}

LANGUAGE_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Ruby": "#701516",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Python": "#3572A5",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "SCSS": "#c6538c",
    "PHP": "#4F5D95",
    "Vue": "#41b883",
    "Go": "#00ADD8",
    "Java": "#b07219",
    "C#": "#178600",
    "C++": "#f34b7d",
}
FALLBACK_COLORS = ["#70a5fd", "#38bdae", "#bb9af7", "#ff9e64", "#7dcfff", "#9ece6a", "#e0af68", "#f7768e"]


def fetch_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if PROFILE_TOKEN:
        headers["Authorization"] = f"Bearer {PROFILE_TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_repositories():
    repositories = []
    page = 1

    while True:
        if PROFILE_TOKEN:
            url = (
                f"{API_ROOT}/user/repos?visibility=all&affiliation=owner"
                f"&sort=pushed&per_page=100&page={page}"
            )
        else:
            url = (
                f"{API_ROOT}/users/{USERNAME}/repos?type=owner"
                f"&sort=pushed&per_page=100&page={page}"
            )

        batch = fetch_json(url)
        repositories.extend(
            repo
            for repo in batch
            if repo.get("owner", {}).get("login", "").lower() == USERNAME.lower()
        )
        if len(batch) < 100:
            break
        page += 1

    return repositories


def metric(label: str, value: str, x: int, y: int) -> str:
    return f"""
    <g transform="translate({x}, {y})">
      <text class="label" x="0" y="0">{html.escape(label)}</text>
      <text class="value" x="0" y="28">{html.escape(str(value))}</text>
    </g>"""


def generate_stats(user, repositories):
    private_count = sum(1 for repo in repositories if repo.get("private"))
    public_count = sum(1 for repo in repositories if not repo.get("private"))
    stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
    forks = sum(repo.get("forks_count", 0) for repo in repositories)
    followers = user.get("followers", 0)
    display_name = DISPLAY_NAME

    if PROFILE_TOKEN:
        coverage = "private + public owned repositories"
        metrics = [
            ("Repositories", f"{len(repositories):,}"),
            ("Private repos", f"{private_count:,}"),
            ("Stars earned", f"{stars:,}"),
            ("Followers", f"{followers:,}"),
        ]
    else:
        coverage = "public owned repositories only"
        metrics = [
            ("Public repos", f"{public_count:,}"),
            ("Stars earned", f"{stars:,}"),
            ("Repository forks", f"{forks:,}"),
            ("Followers", f"{followers:,}"),
        ]

    svg = f"""<svg width="520" height="190" viewBox="0 0 520 190" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(display_name)}'s GitHub stats</title>
  <desc id="desc">GitHub statistics for @{html.escape(USERNAME)} using {html.escape(coverage)}</desc>
  <style>
    .title {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #70a5fd; }}
    .handle {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9b1d6; }}
    .label {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #38bdae; }}
    .value {{ font: 700 22px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .note {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #787c99; }}
  </style>
  <rect x="0.5" y="0.5" width="519" height="189" rx="6" fill="#1a1b27" stroke="#30363d"/>
  <text class="title" x="24" y="34">{html.escape(display_name)}'s GitHub Stats</text>
  <text class="handle" x="24" y="54">@{html.escape(USERNAME)} · {html.escape(coverage)}</text>
  {metric(metrics[0][0], metrics[0][1], 24, 92)}
  {metric(metrics[1][0], metrics[1][1], 154, 92)}
  {metric(metrics[2][0], metrics[2][1], 284, 92)}
  {metric(metrics[3][0], metrics[3][1], 414, 92)}
  <text class="note" x="24" y="164">Private repository names and contents are never rendered in this card.</text>
</svg>
"""
    STATS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATS_OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {STATS_OUTPUT}")


def include_in_language_profile(repo):
    if repo.get("fork") or repo.get("archived"):
        return False
    return repo.get("name", "") not in LANGUAGE_EXCLUDED_REPOS


def generate_languages(repositories):
    totals = defaultdict(int)
    source_repositories = [repo for repo in repositories if include_in_language_profile(repo)]

    print(
        f"Language profile: {len(source_repositories)} repositories included; "
        f"{len(repositories) - len(source_repositories)} excluded."
    )

    for repo in source_repositories:
        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        try:
            language_bytes = fetch_json(languages_url)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            print(f"Skipping languages for {repo.get('name')}: {exc}")
            continue
        for language, byte_count in language_bytes.items():
            totals[language] += int(byte_count)

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    total_bytes = sum(value for _, value in ranked) or 1
    coverage = "private + public project repos" if PROFILE_TOKEN else "public project repos"

    segments = []
    cursor = 24.0
    bar_width = 472.0
    for index, (language, value) in enumerate(ranked):
        width = bar_width * value / total_bytes
        color = LANGUAGE_COLORS.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])
        segments.append(
            f'<rect x="{cursor:.2f}" y="70" width="{max(width, 1):.2f}" height="9" fill="{color}"/>'
        )
        cursor += width

    labels = []
    for index, (language, value) in enumerate(ranked):
        percentage = value / total_bytes * 100
        column = 0 if index < 4 else 1
        row = index if index < 4 else index - 4
        x = 24 + column * 246
        y = 108 + row * 24
        color = LANGUAGE_COLORS.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])
        labels.append(
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text class="lang" x="{x + 18}" y="{y}">{html.escape(language)} {percentage:.1f}%</text>'
        )

    if not ranked:
        labels.append('<text class="lang" x="24" y="112">No language data available.</text>')

    svg = f"""<svg width="520" height="220" viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Most used languages</title>
  <desc id="desc">Language distribution across @{html.escape(USERNAME)}'s {html.escape(coverage)}</desc>
  <style>
    .title {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #70a5fd; }}
    .subtitle {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9b1d6; }}
    .lang {{ font: 500 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #38bdae; }}
    .note {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #787c99; }}
  </style>
  <rect x="0.5" y="0.5" width="519" height="219" rx="6" fill="#1a1b27" stroke="#30363d"/>
  <text class="title" x="24" y="34">Most Used Languages</text>
  <text class="subtitle" x="24" y="54">Authored/project repositories · {html.escape(coverage)}</text>
  <clipPath id="bar"><rect x="24" y="70" width="472" height="9" rx="4.5"/></clipPath>
  <g clip-path="url(#bar)">{''.join(segments)}</g>
  {''.join(labels)}
  <text class="note" x="24" y="204">Excludes forks, mirrors, legacy/vendor-heavy code and asset-only repositories.</text>
</svg>
"""

    LANGS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    LANGS_OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {LANGS_OUTPUT}")


def main():
    user = fetch_json(f"{API_ROOT}/users/{USERNAME}")
    repositories = fetch_repositories()
    generate_stats(user, repositories)
    generate_languages(repositories)


if __name__ == "__main__":
    main()
