from collections import ChainMap
from functools import wraps
import requests

# GitLab user authentication token
token = ''


# TODO there is probably an idiomatic way to do this in requests but too lazy
#      to look it up
class AuthedRequests:
    def __getattr__(self, name):
        requests_function = getattr(requests, name)

        @wraps(requests_function)
        def authed_requests_function(*args, **kwargs):
            headers = {'Authorization': f'Bearer {token}'}
            kwargs2 = ChainMap(dict(headers=headers), kwargs)
            try:
                r = requests_function(*args, **kwargs2)
                r.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise SystemExit(e)
            return r

        return authed_requests_function


authed_requests = AuthedRequests()


def get_repos():
    """Finds all public GitLab repositories of authenticated user.

    Returns:
     - List of public GitLab repositories.
    """

    url = 'https://gitlab.com/api/v4/projects?visibility=public&owned=true&archived=false'

    try:
        r = authed_requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()


def get_user():
    url = 'https://gitlab.com/api/v4/user'

    try:
        r = authed_requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()


def get_repo_by_shorthand(shorthand):
    if "/" not in shorthand:
        user = get_user()["username"]
        namespace, project = user, shorthand
    else:
        namespace, project = shorthand.rsplit("/", maxsplit=1)

    project_id = requests.utils.quote("/".join([namespace, project]), safe="")

    url = f'https://gitlab.com/api/v4/projects/{project_id}'

    try:
        r = authed_requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()



def get_mirrors(gitlab_repo):
    """Finds all configured mirrors of GitLab repository.

    Args:
     - gitlab_repo: GitLab repository.

    Returns:
     - List of mirrors.
    """

    url = f'https://gitlab.com/api/v4/projects/{gitlab_repo["id"]}/remote_mirrors'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()


def mirror_target_exists(github_repos, mirrors):
    """Checks if any of the given mirrors points to any of the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - mirrors: List of mirrors configured for a single GitLab repository.

    Returns:
     - True if any of the mirror points to an existing GitHub repository, False otherwise.
    """

    for mirror in mirrors:
        if any(mirror['url'] and mirror['url'].endswith(f'{repo["full_name"]}.git') for repo in github_repos):
            return True

    return False


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

    url = f'https://gitlab.com/api/v4/projects/{gitlab_repo["id"]}/remote_mirrors'
    headers = {'Authorization': f'Bearer {token}'}

    # If github-user is not provided use the gitlab username
    if not github_user:
        github_user = gitlab_repo['owner']['username']

    data = {
        'url': f'https://{github_user}:{github_token}@github.com/{github_user}/{gitlab_repo["path"]}.git',
        'enabled': True
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()
