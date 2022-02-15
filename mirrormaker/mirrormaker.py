from collections import namedtuple
from tabulate import tabulate
import typer
from tqdm import tqdm
from typing import Optional
from . import __version__
from . import gitlab
from . import github


app = typer.Typer()


@app.callback(context_settings={'auto_envvar_prefix': 'MIRRORMAKER'})
def mirrormaker(
    github_token: str = typer.Option(
        ...,
        help='GitHub authentication token',
    ),
    gitlab_token: str = typer.Option(
        ...,
        help='GitLab authentication token',
    ),
    github_user: Optional[str] = typer.Option(
        None,
        help='GitHub username. If not provided, your GitLab username will be used by default.'
    ),
):
    github.token = github_token
    github.user = github_user
    gitlab.token = gitlab_token


@app.command("list")
def list_repos_and_mirrors(
    repo: Optional[str] = typer.Argument(
        None,
        help='Specific repository to list.'
    )
):
    """
    List repositories and their mirror status.
    """
    gitlab_repos, github_repos = _get_repos(github_forks=True,
        gitlab_repo=repo)

    actions = find_actions_to_perform(gitlab_repos, github_repos)

    print_summary_table(actions)


@app.command()
def mirror(
    target_forks: bool = typer.Option(
        False,
        help="Allow forks as target repos for pushing."
    ),
    dry_run: bool = typer.Option(
        False,
        help="If enabled, a summary will be printed and no mirrors will be created."
    ),
    repo: Optional[str] = typer.Argument(
        None,
        help='Specific repository to set up mirror for. Can be either '
        'a simple project name ("myproject"), in which case its namespace is assumed to '
        'be the current user, or the path of a project under a specific namespace '
        '("mynamespace/myproject"). If unspecified, mirrors will be created for all repos.'
    )
):
    """
    Set up mirroring of repositories from GitLab to GitHub.

    By default, mirrors for all repositories owned by the user will be set up.

    If the REPO argument is given, a mirror will be set up for that repository
    only. REPO can be either a simple project name ("myproject"), in which case
    its namespace is assumed to be the current user, or the path of a project
    under a specific namespace ("mynamespace/myproject").
    """
    gitlab_repos, github_repos = _get_repos(github_forks=True,
        gitlab_repo=repo)

    actions = find_actions_to_perform(gitlab_repos, github_repos)

    print_summary_table(actions)

    perform_actions(actions, dry_run)

    typer.echo('Done!')


AllRepos = namedtuple("AllRepos", ["gitlab_repos", "github_repos"])
def _get_repos(github_forks=False, gitlab_repo=None) -> AllRepos:
    github.target_forks = github_forks

    if gitlab_repo:
        gitlab_repos = [gitlab.get_repo_by_shorthand(gitlab_repo)]
    else:
        typer.echo('Getting your public GitLab repositories')
        gitlab_repos = gitlab.get_repos()
        if not gitlab_repos:
            typer.echo('There are no public repositories in your GitLab account.')
            return

    typer.echo('Getting your public GitHub repositories')
    github_repos = github.get_repos()

    return AllRepos(gitlab_repos=gitlab_repos, github_repos=github_repos)


def _mirror(target_forks=False, dry_run=True, repo=None):
    gitlab_repos, github_repos = _get_repos(github_forks=True,
        gitlab_repo=repo)

    actions = find_actions_to_perform(gitlab_repos, github_repos)

    print_summary_table(actions)

    perform_actions(actions, dry_run)

    typer.echo('Done!')


def find_actions_to_perform(gitlab_repos, github_repos):
    """Goes over provided repositories and figure out what needs to be done to create missing mirrors.

    Args:
     - gitlab_repos: List of GitLab repositories.
     - github_repos: List of GitHub repositories.

    Returns:
     - actions: List of actions necessary to perform on a GitLab repo to create a mirror
                eg: {'gitlab_repo: '', 'create_github': True, 'create_mirror': True}
    """

    actions = []
    for gitlab_repo in tqdm(gitlab_repos, desc='Checking mirrors status'):
        action = check_mirror_status(gitlab_repo, github_repos)
        actions.append(action)

    return actions


def check_mirror_status(gitlab_repo, github_repos):
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.

    Returns:
     - action: Action necessary to perform on a GitLab repo to create a mirror (see find_actions_to_perform())
    """

    action = {'gitlab_repo': gitlab_repo, 'create_github': True, 'create_mirror': True}

    mirrors = gitlab.get_mirrors(gitlab_repo)
    if gitlab.mirror_target_exists(github_repos, mirrors):
        action['create_github'] = False
        action['create_mirror'] = False
        return action

    if github.repo_exists(github_repos, gitlab_repo.path_with_namespace):
        action['create_github'] = False

    return action


def print_summary_table(actions):
    """Prints a table summarizing whether mirrors are already created or missing
    """

    typer.echo('Your mirrors status summary:\n')

    created = typer.style(u'\u2714 created', fg='green')
    missing = typer.style(u'\u2718 missing', fg='red')

    headers = ['GitLab repo', 'GitHub repo', 'Mirror']
    summary = []

    for action in actions:
        row = [action["gitlab_repo"].path_with_namespace]
        row.append(missing) if action["create_github"] else row.append(created)
        row.append(missing) if action["create_mirror"] else row.append(created)
        summary.append(row)

    summary.sort()

    typer.echo(tabulate(summary, headers) + '\n')


def perform_actions(actions, dry_run):
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
    """

    if dry_run:
        typer.echo('Run without the --dry-run flag to create missing repositories and mirrors.')
        return

    for action in tqdm(actions, desc='Creating mirrors'):
        if action["create_github"]:
            github.create_repo(action["gitlab_repo"])

        if action["create_mirror"]:
            gitlab.create_mirror(action["gitlab_repo"], github.token, github.user)


def main():
    app()


if __name__ == '__main__':
    main()
