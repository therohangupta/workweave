import requests
import os

TOKEN = os.environ.get("GITHUB_TOKEN")

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

query = """
{
  viewer {
    login
  }
}
"""

res = requests.post(
    "https://api.github.com/graphql",
    json={"query": query},
    headers=headers
)

print(res.json())