SEARCH_PRS_QUERY = """
query SearchPullRequests($queryString: String!, $cursor: String) {
  search(query: $queryString, type: ISSUE, first: 50, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        number
        title
        url
        createdAt
        mergedAt
        closedAt
        state
        additions
        deletions
        changedFiles
        author {
          login
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
        files(first: 100) {
          nodes {
            path
          }
        }
        reviews(first: 100) {
          nodes {
            state
            createdAt
            author {
              login
            }
          }
        }
        comments(first: 100) {
          nodes {
            createdAt
            author {
              login
            }
          }
        }
      }
    }
  }
}
"""
