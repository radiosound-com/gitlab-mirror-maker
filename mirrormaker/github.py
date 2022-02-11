from github import Github

# GitHub user authentication token
token = ''

# GitHub username (under this user namespace the mirrors will be created)
user = ''


def get_repos():
    """Finds all public GitHub repositories (which are not forks) of authenticated user.

    Returns:
     - List of public GitHub repositories.
    """

    gh = Github(token)

    # Return only non forked public repositories
    return [ x for x in gh.get_user().get_repos(type="public") if not x.fork ]


def repo_exists(github_repos, repo_slug):
    """Checks if a repository with a given slug exists among the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - repo_slug: Repository slug (usually in a form of path with a namespace, eg: "username/reponame").

    Returns:
     - True if repository exists, False otherwise.
    """

    return any(repo.full_name == repo_slug for repo in github_repos)


def create_repo(gitlab_repo):
    """Creates GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.

    Returns:
     - JSON representation of created GitHub repo.
    """

    gh = Github(base_url="https://github.com/api/v3", login_or_token=token)

    data = {
        'name': gitlab_repo['path'],
        'description': f'{gitlab_repo["description"]} [mirror]',
        'homepage': gitlab_repo['web_url'],
        'private': False,
        'has_wiki': False,
        'has_projects': False
    }

    return gh.get_user().create_repo(**data)
