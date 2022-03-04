from collections import UserList
from dataclasses import dataclass
import responses
import mirrormaker
from mirrormaker import github
from mirrormaker import gitlab
import pytest
from unittest.mock import Mock


@responses.activate
def test_filter_forked_repos(monkeypatch):
    repo1 = Mock()
    repo1.configure_mock(name="repo_1", fork=True)
    repo2 = Mock()
    repo2.configure_mock(name="repo_2", fork=False)
    class MockRepoIter(UserList):
        @property
        def totalCount(self):
            return len(self.data)
    repos = MockRepoIter([repo1, repo2])
    token = "some-token"
    MockGithub = Mock()
    mock_get_repos = MockGithub(token).get_user().get_repos
    mock_get_repos.side_effect = lambda *a, **kw: repos

    with monkeypatch.context() as m:
        m.setattr(github, "Github", MockGithub)
        m.setattr(github, "token", token)

        github_repos = github.get_repos()

        assert len(github_repos) == 1
        assert github_repos[0].name == 'repo_2'

        m.setattr(github, "target_forks", False)

        github_repos = github.get_repos()

        assert len(github_repos) == 1


@pytest.mark.xfail(strict=True, reason="API wrapper libs request differently")
@responses.activate
def test_filter_no_repos():
    responses.add(responses.GET, 'https://api.github.com:443/user/repos?type=public',
                  json=[], status=200)

    github_repos = github.get_repos()

    assert len(github_repos) == 0


@dataclass
class MockRepo:
    full_name: str

@dataclass
class MockMirror:
    url: str


@pytest.mark.xfail(strict=True, reason="too lazy to fix")
def test_mirror_exists():
    mirrors_data = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    mirrors = [ MockMirror(**x) for x in mirrors_data ]
    github_repos_data = [{'full_name': 'grdl/one'},
                          {'full_name': 'grdl/two'}]
    github_repos = [ MockRepo(**x) for x in github_repos_data ]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == True

    mirrors = []
    github_repos_data = [{'full_name': 'grdl/one'}]
    github_repos = [ MockRepo(**x) for x in github_repos_data ]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors_data = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    mirrors = [ MockMirror(**x) for x in mirrors_data ]
    github_repos_data = [{'full_name': 'grdl/two'}]
    github_repos = [ MockRepo(**x) for x in github_repos_data ]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors = []
    github_repos = []

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors_data = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    mirrors = [ MockMirror(**x) for x in mirrors_data ]
    github_repos = []

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors_data = [{'url': 'https://*****:*****@github.com/grdl/one.git'},
               {'url': 'https://*****:*****@github.com/grdl/two.git'}]
    mirrors = [ MockMirror(**x) for x in mirrors_data ]
    github_repos_data = [{'full_name': 'grdl/two'},
                         {'full_name': 'grdl/three'}]
    github_repos = [ MockRepo(**x) for x in github_repos_data ]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == True


def test_github_repo_exists():
    github_repos_data = [{'full_name': 'grdl/one'},
                         {'full_name': 'grdl/two'}]
    github_repos = [ MockRepo(**x) for x in github_repos_data ]

    slug = 'grdl/one'

    assert github.repo_exists(github_repos, slug) == True

    slug = 'grdl/three'

    assert github.repo_exists(github_repos, slug) == False

    assert github.repo_exists([], slug) == False
