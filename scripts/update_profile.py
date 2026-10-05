import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import requests

USERNAME = "harshad1234u"
ROOT = Path(__file__).resolve().parents[1]
TOKEN = os.environ["GITHUB_TOKEN"]

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2026-03-10",
}

API = "https://api.github.com"


def get(url, params=None):
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def graphql(query, variables):
    response = requests.post(
        "https://api.github.com/graphql",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"query": query, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def update_svg(filename, values):
    """
    Update the value tspan immediately following each statistic label.

    Uses deterministic string parsing rather than a whole-line regex because
    several statistics share one SVG <text> element.
    """
    path = ROOT / filename
    content = path.read_text(encoding="utf-8")

    for label, value in values.items():
        marker = f". {label}: </tspan>"
        label_start = content.find(marker)

        if label_start == -1:
            raise RuntimeError(f"Could not find SVG statistic: {label}")

        # The label is followed by a padding tspan and then the value tspan.
        padding_start = label_start + len(marker)
        padding_open = content.find("<tspan", padding_start)
        if padding_open == -1:
            raise RuntimeError(f"Could not find SVG padding field: {label}")

        padding_close = content.find("</tspan>", padding_open)
        if padding_close == -1:
            raise RuntimeError(f"Could not close SVG padding field: {label}")

        value_open = content.find("<tspan", padding_close + len("</tspan>"))
        if value_open == -1:
            raise RuntimeError(f"Could not find SVG value field: {label}")

        value_content_start = content.find(">", value_open) + 1
        value_close = content.find("</tspan>", value_content_start)

        if value_content_start <= 0 or value_close == -1:
            raise RuntimeError(f"Could not parse SVG value field: {label}")

        content = (
            content[:value_content_start]
            + escape(str(value))
            + content[value_close:]
        )

    path.write_text(content, encoding="utf-8")
    print(f"Updated {filename}")


def update_readme_cache_buster():
    """
    Change the SVG query-string version on every successful stats refresh.
    GitHub can cache rendered README images, so a new URL forces the profile
    README to fetch the latest SVG instead of showing an older cached image.
    """
    path = ROOT / "ReadMe.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    replacements = {
        'srcset="dark_mode.svg': f'srcset="dark_mode.svg?v={version}',
        'srcset="light_mode.svg': f'srcset="light_mode.svg?v={version}',
        'src="dark_mode.svg': f'src="dark_mode.svg?v={version}',
    }

    found = {key: False for key in replacements}

    for i, line in enumerate(lines):
        for old_prefix, new_prefix in replacements.items():
            if old_prefix in line:
                start = line.index(old_prefix)
                quote_end = line.index('"', start + len(old_prefix))
                lines[i] = line[:start] + new_prefix + line[quote_end:]
                found[old_prefix] = True

    if not all(found.values()):
        missing = [key for key, value in found.items() if not value]
        raise RuntimeError(f"Could not update README SVG cache-buster: {missing}")

    path.write_text("".join(lines), encoding="utf-8")
    print(f"README SVG cache version: {version}")


# ---------------------------------------------------------
# Public profile statistics
# Updated automatically by GitHub Actions.\n# Profile stats are refreshed safely on every scheduled run.\n# README SVG URLs are cache-busted after each refresh.
# ---------------------------------------------------------

user = get(f"{API}/users/{USERNAME}")

repos = user.get("public_repos", 0)
followers = user.get("followers", 0)

# Fetch all owned public repositories. The endpoint is paginated, so do not
# assume the account will always fit in a single 100-item response.
repositories = []
page = 1

while True:
    batch = get(
        f"{API}/users/{USERNAME}/repos",
        {
            "per_page": 100,
            "page": page,
            "type": "owner",
            "sort": "updated",
        },
    )
    repositories.extend(batch)

    if len(batch) < 100:
        break

    page += 1

stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
forks = sum(repo.get("forks_count", 0) for repo in repositories)

top_repo = max(
    repositories,
    key=lambda repo: (
        repo.get("stargazers_count", 0),
        repo.get("name", "").lower(),
    ),
    default=None,
)

top_repo_name = top_repo.get("name", "N/A") if top_repo else "N/A"
top_repo_stars = top_repo.get("stargazers_count", 0) if top_repo else 0


# ---------------------------------------------------------
# Public PR / issue totals
# ---------------------------------------------------------

pr_count = get(
    f"{API}/search/issues",
    {"q": f"author:{USERNAME} type:pr", "per_page": 1},
).get("total_count", 0)

issue_count = get(
    f"{API}/search/issues",
    {"q": f"author:{USERNAME} type:issue", "per_page": 1},
).get("total_count", 0)


# ---------------------------------------------------------
# Last 12 months contribution statistics
# ---------------------------------------------------------

now = datetime.now(timezone.utc)
year_ago = now - timedelta(days=365)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
      }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
      restrictedContributionsCount
    }
  }
}
"""

collection = graphql(
    query,
    {
        "login": USERNAME,
        "from": year_ago.isoformat(),
        "to": now.isoformat(),
    },
)["user"]["contributionsCollection"]

# totalContributions belongs to ContributionCalendar, not
# ContributionsCollection. GitHub's current GraphQL schema exposes the
# calendar total, plus the individual contribution totals below.
commits_12m = collection["totalCommitContributions"]
contributions_12m = collection["contributionCalendar"]["totalContributions"]
contributed_repos_12m = collection["totalRepositoriesWithContributedCommits"]
reviews_12m = collection["totalPullRequestReviewContributions"]
private_contributions = collection["restrictedContributionsCount"]


# ---------------------------------------------------------
# Replace every dynamic value in both SVG themes
# ---------------------------------------------------------

values = {
    "Repos": repos,
    "Stars": stars,
    "Forks": forks,
    "Followers": followers,
    "Commits": commits_12m,
    "Contributed": contributed_repos_12m,
    "PRs": pr_count,
    "Issues": issue_count,
    "Contributions": contributions_12m,
    "Reviews": reviews_12m,
    "Private": private_contributions,
    "Top repo": f"{top_repo_name} ({top_repo_stars} ★)",
}

update_svg("dark_mode.svg", values)
update_svg("light_mode.svg", values)
update_readme_cache_buster()

print()
print("GitHub profile updated successfully")
print(f"Repositories         : {repos}")
print(f"Stars                : {stars}")
print(f"Forks                : {forks}")
print(f"Followers            : {followers}")
print(f"Commits (12 months)  : {commits_12m}")
print(f"Contributions (12m)  : {contributions_12m}")
print(f"Contributed repos    : {contributed_repos_12m}")
print(f"Pull Requests        : {pr_count}")
print(f"Issues               : {issue_count}")
print(f"Reviews (12 months)  : {reviews_12m}")
print(f"Private contributions: {private_contributions}")
print(f"Top repository       : {top_repo_name} ({top_repo_stars} ★)")
