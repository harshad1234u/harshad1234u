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
    Update the value tspan on the line containing each labelled statistic.

    This intentionally does not use one-time placeholders. The SVGs already
    contain rendered values, so matching by label makes the operation
    idempotent and allows every scheduled run to refresh the current value.
    """
    path = ROOT / filename
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    for label, value in values.items():
        marker = f". {label}: </tspan>"
        line_index = next(
            (i for i, line in enumerate(lines) if marker in line),
            None,
        )
        if line_index is None:
            raise RuntimeError(f"Could not find SVG statistic: {label}")

        line = lines[line_index]
        matches = list(re.finditer(r"<tspan[^>]*>([^<]*)</tspan>", line))
        if not matches:
            raise RuntimeError(f"Could not find SVG value field: {label}")

        # The final tspan on each statistics line is the displayed value.
        value_match = matches[-1]
        value_text = escape(str(value))
        start, end = value_match.span(1)
        lines[line_index] = line[:start] + value_text + line[end:]

    path.write_text("".join(lines), encoding="utf-8")
    print(f"Updated {filename}")


# ---------------------------------------------------------
# Public profile statistics
# Updated automatically by GitHub Actions.
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
