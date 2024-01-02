from github import Github
from .tqdm import tqdm

# GitHub user authentication token
token = ''

# GitHub username (under this user namespace the mirrors will be created)
user = 'radiosound-com'

target_forks = False


def get_repos():
    """Finds all public GitHub repositories (which are not forks) of authenticated user.

    Returns:
     - List of public GitHub repositories.
    """

    gh = Github(token)

    # Return only public non forked repositories unless target_forks is set
    #repos_iter = gh.get_user().get_repos(type="public")
    #repos_tqdm = tqdm(repos_iter, total=repos_iter.totalCount, desc="GitHub repos")
    org = gh.get_organization('radiosound-com')
    repos_iter = org.get_repos()
    repos_iter
    repos_tqdm = tqdm(repos_iter, total=repos_iter.totalCount, desc="GitHub repos")

    return [ x for x in repos_tqdm if not x.fork or target_forks ]


def repo_exists(github_repos, repo_slug):
    """Checks if a repository with a given slug exists among the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - repo_slug: Repository slug (usually in a form of path with a namespace, eg: "username/reponame").

    Returns:
     - True if repository exists, False otherwise.
    """

    return any(repo.full_name == repo_slug for repo in github_repos)


def get_repo_by_slug(github_repos, repo_slug):
    l = [repo for repo in github_repos if repo.full_name.endswith(f'/{repo_slug}')]
    return l[0] if len(l) > 0 else None


def create_repo(gitlab_repo):
    """Creates GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.

    Returns:
     - JSON representation of created GitHub repo.
    """

    gh = Github(token)

    path = gitlab_repo.path_with_namespace.replace('/', '_')

    data = {
        'name': path,
        'description': f'{gitlab_repo.description} [mirror]',
        'homepage': gitlab_repo.web_url,
        'private': True,
        'has_wiki': False,
        'has_projects': False
    }

    org = gh.get_organization('radiosound-com')

    return org.create_repo(**data)


def set_description(github_repo, description):
    github_repo.edit(description=description)


def set_website(github_repo, website):
    github_repo.edit(homepage=website)
