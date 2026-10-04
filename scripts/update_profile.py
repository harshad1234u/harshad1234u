import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

USERNAME = "harshad1234u"
ROOT = Path(__file__).resolve().parents[1]
TOKEN = os.environ["GITHUB_TOKEN"]

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
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
    path = ROOT / filename
    content = path.read_text(encoding="utf-8")

    for placeholder, value in values.items():
        content = content.replace(placeholder, str(value))

    path.write_text(content, encoding="utf-8")
    print(f"Updated {filename}")


# ---------------------------------------------------------
# Public profile statistics
# ---------------------------------------------------------

user = get(f"{API}/users/{USERNAME}")

repos = user.get("public_repos", 0)
followers = user.get("followers", 0)

repositories = get(
    f"{API}/users/{USERNAME}/repos",
    {"per_page": 100, "type": "owner", "sort": "updated"},
)

stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
forks = sum(repo.get("forks_count", 0) for repo in repositories)

top_repo = max(
    repositories,
    key=lambda repo: repo.get("stargazers_count", 0),
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
      totalCommitContributions
      totalPullRequestReviewContributions
      totalContributions
      restrictedContributionsCount
      totalRepositoriesWithContributedCommits
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

commits_12m = collection.get("totalCommitContributions", 0)
reviews_12m = collection.get("totalPullRequestReviewContributions", 0)
contributions_12m = collection.get("totalContributions", 0)

# This is the number of different repositories in which the user
# contributed commits during the last 12 months.
contributed_repos_12m = collection.get(
    "totalRepositoriesWithContributedCommits", 0
)

# GitHub only exposes restricted/private contribution counts when
# the account has enabled private contribution visibility.
private_contributions = collection.get("restrictedContributionsCount", 0)


# ---------------------------------------------------------
# Replace every dynamic value in both SVG themes
# ---------------------------------------------------------

values = {
    "REPOS_VALUE": repos,
    "STARS_VALUE": stars,
    "FORKS_VALUE": forks,
    "FOLLOWERS_VALUE": followers,
    "COMMITS_VALUE": commits_12m,
    "CONTRIBUTED_VALUE": contributed_repos_12m,
    "PRS_VALUE": pr_count,
    "ISSUES_VALUE": issue_count,
    "CONTRIBUTIONS_VALUE": contributions_12m,
    "REVIEWS_VALUE": reviews_12m,
    "PRIVATE_VALUE": private_contributions,
    "TOP_REPO_VALUE": f"{top_repo_name} ({top_repo_stars} ★)",
}

update_svg("dark_mode.svg", values)
update_svg("light_mode.svg", values)

print()
print("GitHub profile updated successfully")
print(f"Repositories        : {repos}")
print(f"Stars               : {stars}")
print(f"Forks               : {forks}")
print(f"Followers           : {followers}")
print(f"Commits (12 months) : {commits_12m}")
print(f"Contributions (12m) : {contributions_12m}")
print(f"Contributed repos   : {contributed_repos_12m}")
print(f"Pull Requests       : {pr_count}")
print(f"Issues              : {issue_count}")
print(f"Reviews (12 months) : {reviews_12m}")
print(f"Private contributions: {private_contributions}")
print(f"Top repository      : {top_repo_name} ({top_repo_stars} ★)")
