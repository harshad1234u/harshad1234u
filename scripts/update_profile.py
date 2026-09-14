import os
import re
import requests

USERNAME = "harshad1234u"

TOKEN = os.environ["GITHUB_TOKEN"]

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get(url, params=None):
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------
# GitHub profile
# ---------------------------------------------------------

user = get(f"https://api.github.com/users/{USERNAME}")

followers = user["followers"]
following = user["following"]
repos = user["public_repos"]


# ---------------------------------------------------------
# Repositories
# ---------------------------------------------------------

repositories = get(
    f"https://api.github.com/users/{USERNAME}/repos",
    {
        "per_page": 100,
        "type": "owner",
    },
)

stars = sum(
    repo["stargazers_count"]
    for repo in repositories
)

forks = sum(
    repo["forks_count"]
    for repo in repositories
)


# ---------------------------------------------------------
# Pull requests
# ---------------------------------------------------------

prs = get(
    "https://api.github.com/search/issues",
    {
        "q": f"author:{USERNAME} type:pr",
        "per_page": 1,
    },
)

pr_count = prs["total_count"]


# ---------------------------------------------------------
# Issues
# ---------------------------------------------------------

issues = get(
    "https://api.github.com/search/issues",
    {
        "q": f"author:{USERNAME} type:issue",
        "per_page": 1,
    },
)

issue_count = issues["total_count"]


# ---------------------------------------------------------
# Values used by SVG
# ---------------------------------------------------------

values = {
    "REPOS_VALUE": repos,
    "STARS_VALUE": stars,
    "FORKS_VALUE": forks,
    "FOLLOWERS_VALUE": followers,
    "CONTRIBUTED_VALUE": following,
    "PRS_VALUE": pr_count,
    "ISSUES_VALUE": issue_count,
}


# ---------------------------------------------------------
# Update SVG
# ---------------------------------------------------------

def update_svg(filename):

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    for placeholder, value in values.items():
        content = content.replace(
            placeholder,
            str(value)
        )

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated {filename}")


update_svg("dark_mode.svg")
update_svg("light_mode.svg")

print()
print("GitHub profile updated:")
print(f"Repositories : {repos}")
print(f"Stars        : {stars}")
print(f"Forks        : {forks}")
print(f"Followers    : {followers}")
print(f"Following    : {following}")
print(f"Pull Requests: {pr_count}")
print(f"Issues       : {issue_count}")
