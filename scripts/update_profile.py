import os
import re
import requests

USERNAME = "harshad1234u"

TOKEN = os.environ.get("GITHUB_TOKEN")

headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github_api(url):
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------
# Get profile information
# ---------------------------------------------------------

user = github_api(
    f"https://api.github.com/users/{USERNAME}"
)

followers = user["followers"]
public_repos = user["public_repos"]


# ---------------------------------------------------------
# Get repositories
# ---------------------------------------------------------

repos = github_api(
    f"https://api.github.com/users/{USERNAME}/repos?per_page=100"
)

stars = sum(
    repo["stargazers_count"]
    for repo in repos
)


# ---------------------------------------------------------
# Values that will be inserted into the SVG
# ---------------------------------------------------------

stats = {
    "REPOS": str(public_repos),
    "STARS": str(stars),
    "FOLLOWERS": str(followers),
}


# ---------------------------------------------------------
# Update SVG
# ---------------------------------------------------------

def update_svg(filename):

    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()

    for key, value in stats.items():

        pattern = rf'({key}=")[^"]*(")'

        content = re.sub(
            pattern,
            rf'\g<1>{value}\g<2>',
            content
        )

    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)


update_svg("dark_mode.svg")
update_svg("light_mode.svg")

print("Profile statistics updated successfully.")
print(stats)
