from dateutil.parser import isoparse
from gitlab import Gitlab
from tqdm import tqdm

# GitLab user authentication token
token = ''


def get_repos():
    """Finds all public GitLab repositories of authenticated user.

    Returns:
     - List of public GitLab repositories.
    """

    gl = Gitlab('https://gitlab.com/', private_token=token)

    repos_iter = gl.projects.list(visibility='public', owned=True,
        archived=False, as_list=False)
    repos = [ repo for repo in tqdm(repos_iter, desc="Repos") ]

    return repos


def get_user():
    gl = Gitlab('https://gitlab.com/', private_token=token)
    gl.auth()

    return gl.user


def get_repo_by_shorthand(shorthand):
    if "/" not in shorthand:
        user = get_user().username
        namespace, project = user, shorthand
    else:
        namespace, project = shorthand.rsplit("/", maxsplit=1)

    gl = Gitlab('https://gitlab.com/', private_token=token)

    project_id = "/".join([namespace, project])

    return gl.projects.get(project_id)


def get_mirrors(gitlab_repo):
    """Finds all configured mirrors of GitLab repository.

    Args:
     - gitlab_repo: GitLab repository.

    Returns:
     - List of mirrors.
    """

    return gitlab_repo.remote_mirrors.list()


def get_github_mirror(github_repos, mirrors):
    """Finds which, if any, of the given mirrors points to any of the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - mirrors: List of mirrors configured for a single GitLab repository.

    Returns:
     - The mirror pointing to one of the GitHub repositories.
    """

    for mirror in mirrors:
        if not mirror.url:
            continue
        for repo in github_repos:
            if mirror.url.endswith(f'/{repo.full_name}.git'):
                return mirror

    return None


def create_mirror(gitlab_repo, github_token, github_user):
    """Creates a push mirror of GitLab repository.

    For more details see: 
    https://docs.gitlab.com/ee/user/project/repository/repository_mirroring.html#pushing-to-a-remote-repository-core

    Args:
     - gitlab_repo: GitLab repository to mirror.
     - github_token: GitHub authentication token.
     - github_user: GitHub username under whose namespace the mirror will be created (defaults to GitLab username if not provided).

    Returns:
     - JSON representation of created mirror.
    """

    # If github-user is not provided use the gitlab username
    if not github_user:
        github_user = gitlab_repo.owner.username

    data = {
        'url': f'https://{github_user}:{github_token}@github.com/{github_user}/{gitlab_repo.path}.git',
        'enabled': True
    }

    mirror = gitlab_repo.remote_mirrors.create(data)

    return mirror


def get_most_recent_commit(gitlab_repo):
    commits = gitlab_repo.commits.list()
    if commits and len(commits) > 0:
        return commits[0]


def get_most_recent_commit_time(gitlab_repo):
    most_recent_commit = get_most_recent_commit(gitlab_repo)
    if most_recent_commit:
        return isoparse(most_recent_commit.committed_date)
