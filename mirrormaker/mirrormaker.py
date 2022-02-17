from collections import namedtuple
from dataclasses import dataclass
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

    statuses = get_mirror_statuses(gitlab_repos, github_repos)

    print_summary_table(statuses)


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

    statuses = get_mirror_statuses(gitlab_repos, github_repos)

    print_summary_table(statuses)

    perform_actions(statuses, dry_run)

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


def get_mirror_statuses(gitlab_repos, github_repos):
    """Goes over provided repositories and figure out their current mirror status

    Args:
     - gitlab_repos: List of GitLab repositories.
     - github_repos: List of GitHub repositories.

    Returns:
     - statuses: Mapping from gitlab_repo to their status
    """

    statuses = {}
    for gitlab_repo in tqdm(gitlab_repos, desc='Checking mirrors status'):
        status = check_mirror_status(gitlab_repo, github_repos)
        statuses[gitlab_repo] = status

    return statuses


@dataclass
class MirrorStatus:
    has_github_repo = False
    has_mirror_configured = False
    last_mirror_push_at = None
    last_mirror_push_succeeded = None
    last_source_commit_at = None

    @property
    def mirror_is_up_to_date(self) -> Optional[bool]:
        if self.last_mirror_push_at is None \
        or self.last_source_commit_at is None:
            return None
        return self.last_source_commit_at < self.last_mirror_push_at


def check_mirror_status(gitlab_repo, github_repos) -> MirrorStatus:
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.

    Returns:
     - status: Status indicating action necessary to perform on a GitLab repo to create a mirror (see get_mirror_statuses())
    """

    status = MirrorStatus()

    mirrors = gitlab.get_mirrors(gitlab_repo)
    if gitlab.mirror_target_exists(github_repos, mirrors):
        status.has_github_repo = True
        status.has_mirror_configured = True
        return status

    if github.repo_exists(github_repos, gitlab_repo.path_with_namespace):
        status.has_github_repo = True

    return status


def print_summary_table(statuses):
    """Prints a table summarizing whether mirrors are already created or missing
    """

    typer.echo('Your mirrors status summary:\n')

    created = typer.style(u'\u2714 created', fg='green')
    missing = typer.style(u'\u2718 missing', fg='red')

    headers = ['GitLab repo', 'GitHub repo', 'Mirror']
    summary = []

    for gitlab_repo, status in statuses.items():
        row = [gitlab_repo.path_with_namespace]
        row.append(missing) if not status.has_github_repo else row.append(created)
        row.append(missing) if not status.has_mirror_configured else row.append(created)
        summary.append(row)

    summary.sort()

    typer.echo(tabulate(summary, headers) + '\n')


def perform_actions(statuses, dry_run):
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
    """

    if dry_run:
        typer.echo('Run without the --dry-run flag to create missing repositories and mirrors.')
        return

    for gitlab_repo, status in tqdm(statuses.items(), desc='Creating mirrors'):
        if not status.has_github_repo:
            github.create_repo(gitlab_repo)

        if not status.has_mirror_configured:
            gitlab.create_mirror(gitlab_repo)


def main():
    app()


if __name__ == '__main__':
    main()
