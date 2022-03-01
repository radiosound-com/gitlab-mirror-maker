from collections import namedtuple
from dateutil.parser import isoparse
from dataclasses import dataclass
from jinja2 import Template
from tabulate import tabulate
import typer
from .tqdm import tqdm
from typing import Optional
from . import __version__
from . import gitlab
from . import github


app = typer.Typer()

description_template = (
    "{% if source_description %}{{source_description}} | {% endif %}"
    "mirror of {{source_url}}"
)

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
    force_update_metadata: bool = typer.Option(
        False,
        help="If enabled, will update metadata like the description and "
        "website URL even if it's already set."
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

    perform_actions(statuses, dry_run,
        force_update_metadata=force_update_metadata)

    typer.echo('Done!')


@app.command()
def show(
    repo: str = typer.Argument(
        ...,
        help='Repository to show info for'
    )
):
    """
    Show info on a GitLab repository and its mirror status.
    """
    gitlab_repos, github_repos = _get_repos(github_forks=True,
        gitlab_repo=repo)

    statuses = get_mirror_statuses(gitlab_repos, github_repos)

    gitlab_repo = gitlab_repos[0]
    status = statuses[gitlab_repo]

    print_repo_info(gitlab_repo, status)


AllRepos = namedtuple("AllRepos", ["gitlab_repos", "github_repos"])
def _get_repos(github_forks=False, gitlab_repo=None) -> AllRepos:
    github.target_forks = github_forks

    if gitlab_repo:
        gitlab_repos = [gitlab.get_repo_by_shorthand(gitlab_repo)]
    else:
        gitlab_repos = gitlab.get_repos()
        if not gitlab_repos:
            typer.echo('There are no public repositories in your GitLab account.')
            return

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
    for gitlab_repo in tqdm(gitlab_repos, desc='Mirror configs'):
        status = check_mirror_status(gitlab_repo, github_repos)
        statuses[gitlab_repo] = status

    return statuses


@dataclass
class MirrorStatus:
    # stuff relevant to mirroring
    github_repo = None
    has_mirror_configured = False
    has_mirror_enabled = False
    last_mirror_push_at = None
    last_mirror_push_succeeded = None
    last_source_commit_at = None
    has_other_mirror = False

    # repo metadata
    description_matches_template = None
    description_is_empty = None

    @property
    def should_have_mirror(self):
        return self.has_github_repo or self.has_mirror_configured

    @property
    def is_up_to_date(self) -> Optional[bool]:
        if self.last_mirror_push_at is None \
        or self.last_source_commit_at is None:
            return None
        return self.last_source_commit_at < self.last_mirror_push_at

    @property
    def has_github_repo(self):
        return self.github_repo is not None

    @property
    def outdated_by(self):
        return (self.last_source_commit_at - self.last_mirror_push_at).total_seconds

    @property
    def is_active_without_issues(self):
        return (self.has_github_repo and self.is_up_to_date
            and self.has_mirror_configured and self.has_mirror_enabled
            and self.is_up_to_date and self.last_mirror_push_succeeded)

    @property
    def no_setup_whatsoever(self):
        return not self.has_github_repo


def build_description(gitlab_repo):
    t = Template(description_template)
    s = dict(
        source_description=gitlab_repo.description,
        source_url=gitlab.get_project_url(gitlab_repo),
    )
    return t.render(s)


def check_mirror_status(gitlab_repo, github_repos) -> MirrorStatus:
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.

    Returns:
     - status: Status indicating action necessary to perform on a GitLab repo to create a mirror (see get_mirror_statuses())
    """

    status = MirrorStatus()

    status.last_source_commit_at = gitlab.get_most_recent_commit_time(gitlab_repo)

    # stuff on the gitlab end
    mirrors = gitlab.get_mirrors(gitlab_repo)
    if (github_mirror := gitlab.get_github_mirror(github_repos, mirrors)):
        status.has_mirror_configured = True
        status.has_mirror_enabled = github_mirror.enabled
        status.last_mirror_push_at = isoparse(github_mirror.last_successful_update_at)
        status.last_mirror_push_succeeded = not github_mirror.last_error
    elif mirrors:
        status.has_other_mirror = True

    # stuff on the github end
    github_repo = github.get_repo_by_slug(github_repos,
        gitlab_repo.path_with_namespace)
    status.github_repo = github_repo

    if github_repo is not None:
        desired_description = build_description(gitlab_repo)
        status.description_matches_template = (
            github_repo.description == desired_description
        )
        status.description_is_empty = not github_repo.description

    return status


def print_summary_table(statuses):
    """Print a table summarizing mirror status.
    """

    def _ok(text):
        return typer.style(f'\u2714 {text}', fg='green')

    def _no(text):
        return typer.style(f'\u2718 {text}', fg='red')

    def _warn(text):
        return typer.style(f'\u26A0 {text}', fg='yellow')

    def _huh(text):
        return typer.style(f'? {text}', fg="blue")

    def _na(text):
        return typer.style(f'- {text}', fg="bright_black")

    headers = ['GitLab repo', 'Mirror', 'Details']
    summary = []

    for gitlab_repo, status in statuses.items():
        row = [gitlab_repo.path_with_namespace]

        if status.is_active_without_issues:
            # summary of overall state
            row.append(_ok("active"))
            # details (minor issues only if active)
            if not status.description_matches_template:
                row.append("description doesn't match template")
            else:
                row.append("")
        elif not status.should_have_mirror:
            # summary of overall state
            row.append(_na("-"))
            # details
            if status.has_other_mirror:
                row.append("has other mirror(s)")
            else:
                row.append("")
        else:
            # summary of overall state
            row.append(_warn("issues"))
            # details
            if not status.has_mirror_configured:
                row.append("GitHub repo exists but no mirror configured")
            elif not status.has_mirror_enabled:
                row.append("mirror disabled")
            elif not status.is_up_to_date:
                row.append("mirror not up to date")
            elif not status.last_mirror_push_succeeded:
                row.append("errors on last push attempt")
            else:
                row.append("unknown issue")

        summary.append(row)

    summary.sort()

    typer.echo(tabulate(summary, headers))


def perform_actions(statuses, dry_run, force_update_metadata=False):
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
     - force_update_metadata (bool): Whether to overwrite metadata like the description even if they're not empty.
    """

    if dry_run:
        typer.echo('Run without the --dry-run flag to create missing repositories and mirrors.')
        return

    for gitlab_repo, status in tqdm(statuses.items(), desc='Creating mirrors'):
        if not status.has_github_repo:
            github.create_repo(gitlab_repo)

        if not status.has_mirror_configured:
            gitlab.create_mirror(gitlab_repo)

        if not status.description_matches_template \
        and (force_update_metadata or status.description_is_empty):
            github.set_description(status.github_repo,
                build_description(gitlab_repo))


def print_repo_info(gitlab_repo, status):
    def _ok(text):
        return typer.style(f'\u2714 {text}', fg='green')

    def _no(text):
        return typer.style(f'\u2718 {text}', fg='red')

    def _na(text):
        return typer.style(f'- {text}', fg="bright_black")

    def _bool(x):
        return _ok("yes") if x else _no("no")

    def _or_na(x, na=""):
        return x if x is not None else _na(na)

    def _datetime_or_none(x):
        if x is None:
            return None
        return x.isoformat(sep=" ", timespec="seconds")

    rows = [
        ["GitLab repo: ", gitlab_repo.path_with_namespace],
        [
            "Last source commit at: ",
            _or_na(_datetime_or_none(status.last_source_commit_at)),
        ],
        [
            "GitHub repo: ",
            status.github_repo.full_name if status.github_repo
                else _bool(False)
        ],
        ["Mirror configured: ", _bool(status.has_mirror_configured)],
        ["Mirror enabled: ", _bool(status.has_mirror_enabled)],
        [
            "Last mirror push succeeded: ",
            _bool(status.last_mirror_push_succeeded)
        ],
        ["Mirror up to date: ", _bool(status.is_up_to_date)],
        [
            "Last mirror push at: ",
            _or_na(_datetime_or_none(status.last_mirror_push_at)),
        ],
        [
            "Description matches template: ",
            _bool(status.description_matches_template)
        ],
        ["Other mirrors: ", _bool(status.has_other_mirror)],
    ]

    typer.echo(tabulate(rows))

def main():
    app()


if __name__ == '__main__':
    main()
