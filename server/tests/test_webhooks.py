from unittest.mock import patch

from flask import Flask

from kraken.server import initdb
from kraken.server.models import db, Project
from kraken.server.bg import jobs as bg_jobs

from dbtest import prepare_db

from kraken.server import webhooks


def _create_app():
    # addresses
    db_url = prepare_db()

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)
    db.create_all(app=app)

    return app


def test_handle_gitea_webhook_push():
    payload = b'{\n  "ref": "refs/heads/master",\n  "before": "20906836a5d8845c5febc634424ee613e7dd6143",\n  "after": "0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n  "compare_url": "http://localhost:3000/gitea/demo/compare/20906836a5d8845c5febc634424ee613e7dd6143...0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n  "commits": [\n    {\n      "id": "0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n      "message": "aaa\\n",\n      "url": "http://localhost:3000/gitea/demo/commit/0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n      "author": {\n        "name": "Michal Nowikowski",\n        "email": "godfryd@gmail.com",\n        "username": "gitea"\n      },\n      "committer": {\n        "name": "Michal Nowikowski",\n        "email": "godfryd@gmail.com",\n        "username": "gitea"\n      },\n      "verification": null,\n      "timestamp": "2021-10-28T06:37:12+02:00",\n      "added": [],\n      "removed": [],\n      "modified": [\n        "README.md"\n      ]\n    }\n  ],\n  "head_commit": {\n    "id": "0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n    "message": "aaa\\n",\n    "url": "http://localhost:3000/gitea/demo/commit/0c43dff0eef13ba0ccc06898fb23d7e58de39591",\n    "author": {\n      "name": "Michal Nowikowski",\n      "email": "godfryd@gmail.com",\n      "username": "gitea"\n    },\n    "committer": {\n      "name": "Michal Nowikowski",\n      "email": "godfryd@gmail.com",\n      "username": "gitea"\n    },\n    "verification": null,\n    "timestamp": "2021-10-28T06:37:12+02:00",\n    "added": [],\n    "removed": [],\n    "modified": [\n      "README.md"\n    ]\n  },\n  "repository": {\n    "id": 1,\n    "owner": {"id":1,"login":"gitea","full_name":"","email":"godfryd@gmail.com","avatar_url":"http://localhost:3000/user/avatar/gitea/-1","language":"","is_admin":false,"last_login":"0001-01-01T00:00:00Z","created":"2021-10-27T07:01:38+02:00","restricted":false,"active":false,"prohibit_login":false,"location":"","website":"","description":"","visibility":"public","followers_count":0,"following_count":0,"starred_repos_count":0,"username":"gitea"},\n    "name": "demo",\n    "full_name": "gitea/demo",\n    "description": "",\n    "empty": false,\n    "private": false,\n    "fork": false,\n    "template": false,\n    "parent": null,\n    "mirror": false,\n    "size": 20,\n    "html_url": "http://localhost:3000/gitea/demo",\n    "ssh_url": "git@localhost:gitea/demo.git",\n    "clone_url": "http://localhost:3000/gitea/demo.git",\n    "original_url": "",\n    "website": "",\n    "stars_count": 0,\n    "forks_count": 0,\n    "watchers_count": 1,\n    "open_issues_count": 0,\n    "open_pr_counter": 0,\n    "release_counter": 0,\n    "default_branch": "master",\n    "archived": false,\n    "created_at": "2021-10-27T07:02:38+02:00",\n    "updated_at": "2021-10-27T07:18:00+02:00",\n    "permissions": {\n      "admin": true,\n      "push": true,\n      "pull": true\n    },\n    "has_issues": true,\n    "internal_tracker": {\n      "enable_time_tracker": true,\n      "allow_only_contributors_to_track_time": true,\n      "enable_issue_dependencies": true\n    },\n    "has_wiki": true,\n    "has_pull_requests": true,\n    "has_projects": true,\n    "ignore_whitespace_conflicts": false,\n    "allow_merge_commits": true,\n    "allow_rebase": true,\n    "allow_rebase_explicit": true,\n    "allow_squash_merge": true,\n    "default_merge_style": "merge",\n    "avatar_url": "",\n    "internal": false,\n    "mirror_interval": ""\n  },\n  "pusher": {"id":1,"login":"gitea","full_name":"","email":"godfryd@gmail.com","avatar_url":"http://localhost:3000/user/avatar/gitea/-1","language":"","is_admin":false,"last_login":"0001-01-01T00:00:00Z","created":"2021-10-27T07:01:38+02:00","restricted":false,"active":false,"prohibit_login":false,"location":"","website":"","description":"","visibility":"public","followers_count":0,"following_count":0,"starred_repos_count":0,"username":"gitea"},\n  "sender": {"id":1,"login":"gitea","full_name":"","email":"godfryd@gmail.com","avatar_url":"http://localhost:3000/user/avatar/gitea/-1","language":"","is_admin":false,"last_login":"0001-01-01T00:00:00Z","created":"2021-10-27T07:01:38+02:00","restricted":false,"active":false,"prohibit_login":false,"location":"","website":"","description":"","visibility":"public","followers_count":0,"following_count":0,"starred_repos_count":0,"username":"gitea"}\n}'

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitea_enabled=True, gitea_secret='q6ca2qimhmfauql5qvje'))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitea_webhook(proj.id, payload, 'push', 'sha1=6d16b1711ed4b6f4fcf01a8cfcf1130bbbc7e794')

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {'after': '0c43dff0eef13ba0ccc06898fb23d7e58de39591',
                                          'before': '20906836a5d8845c5febc634424ee613e7dd6143',
                                          'commits': [{'added': [],
                                                       'author': {'email': 'godfryd@gmail.com',
                                                                  'name': 'Michal Nowikowski',
                                                                  'username': 'gitea'},
                                                       'committer': {'email': 'godfryd@gmail.com',
                                                                     'name': 'Michal Nowikowski',
                                                                     'username': 'gitea'},
                                                       'id': '0c43dff0eef13ba0ccc06898fb23d7e58de39591',
                                                       'message': 'aaa\n',
                                                       'modified': ['README.md'],
                                                       'removed': [],
                                                       'timestamp': '2021-10-28T06:37:12+02:00',
                                                       'url': 'http://localhost:3000/gitea/demo/commit/0c43dff0eef13ba0ccc06898fb23d7e58de39591',
                                                       'verification': None}],
                                          'pusher': {'active': False,
                                                     'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                                     'created': '2021-10-27T07:01:38+02:00',
                                                     'description': '',
                                                     'email': 'godfryd@gmail.com',
                                                     'followers_count': 0,
                                                     'following_count': 0,
                                                     'full_name': '',
                                                     'id': 1,
                                                     'is_admin': False,
                                                     'language': '',
                                                     'last_login': '0001-01-01T00:00:00Z',
                                                     'location': '',
                                                     'login': 'gitea',
                                                     'prohibit_login': False,
                                                     'restricted': False,
                                                     'starred_repos_count': 0,
                                                     'username': 'gitea',
                                                     'visibility': 'public',
                                                     'website': ''},
                                          'ref': 'refs/heads/master',
                                          'repo': 'http://localhost:3000/gitea/demo.git',
                                          'trigger': 'gitea-push'}

        assert content == ''
        assert code == 204


def test_handle_gitea_webhook_pr_open_without_commits():
    event = 'pull_request'
    signature = 'sha1=d65e2feb5dd60ac518f530134ee4a0de96e32fc1'
    with open('tests/gitea-pr-open-without-commits.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitea_enabled=True, gitea_secret='q6ca2qimhmfauql5qvje'))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitea_webhook(proj.id, payload, event, signature)

            ke.assert_not_called()

        assert content == 'pull request with no commits, dropped'
        assert code == 204


def test_handle_gitea_webhook_pr_sync():
    event = 'pull_request'
    signature = 'sha1=1d4f965ec2f536b71209f5cdc28ba763365d2840'
    with open('tests/gitea-pr-sync.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitea_enabled=True, gitea_secret='q6ca2qimhmfauql5qvje'))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitea_webhook(proj.id, payload, event, signature)

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {
                'action': 'synchronized',
                'after': 'f9795c3cd6675f5008e93cfcb42d1d8ee4cc582b',
                'before': 'f44d122982df2cfe3a5491c0e053ae57df732e59',
                'pull_request': {'assignee': None,
                                 'assignees': None,
                                 'base': {'label': 'master',
                                          'ref': 'master',
                                          'repo': {'allow_merge_commits': True,
                                                   'allow_rebase': True,
                                                   'allow_rebase_explicit': True,
                                                   'allow_squash_merge': True,
                                                   'archived': False,
                                                   'avatar_url': '',
                                                   'clone_url': 'http://localhost:3000/gitea/demo.git',
                                                   'created_at': '2021-10-27T07:02:38+02:00',
                                                   'default_branch': 'master',
                                                   'default_merge_style': 'merge',
                                                   'description': '',
                                                   'empty': False,
                                                   'fork': False,
                                                   'forks_count': 0,
                                                   'full_name': 'gitea/demo',
                                                   'has_issues': True,
                                                   'has_projects': True,
                                                   'has_pull_requests': True,
                                                   'has_wiki': True,
                                                   'html_url': 'http://localhost:3000/gitea/demo',
                                                   'id': 1,
                                                   'ignore_whitespace_conflicts': False,
                                                   'internal': False,
                                                   'internal_tracker': {'allow_only_contributors_to_track_time': True,
                                                                        'enable_issue_dependencies': True,
                                                                        'enable_time_tracker': True},
                                                   'mirror': False,
                                                   'mirror_interval': '',
                                                   'name': 'demo',
                                                   'open_issues_count': 0,
                                                   'open_pr_counter': 2,
                                                   'original_url': '',
                                                   'owner': {'active': False,
                                                             'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                                             'created': '2021-10-27T07:01:38+02:00',
                                                             'description': '',
                                                             'email': 'godfryd@gmail.com',
                                                             'followers_count': 0,
                                                             'following_count': 0,
                                                             'full_name': '',
                                                             'id': 1,
                                                             'is_admin': False,
                                                             'language': '',
                                                             'last_login': '0001-01-01T00:00:00Z',
                                                             'location': '',
                                                             'login': 'gitea',
                                                             'prohibit_login': False,
                                                             'restricted': False,
                                                             'starred_repos_count': 0,
                                                             'username': 'gitea',
                                                             'visibility': 'public',
                                                             'website': ''},
                                                   'parent': None,
                                                   'permissions': {'admin': False,
                                                                   'pull': True,
                                                                   'push': False},
                                                   'private': False,
                                                   'release_counter': 0,
                                                   'size': 22,
                                                   'ssh_url': 'git@localhost:gitea/demo.git',
                                                   'stars_count': 0,
                                                   'template': False,
                                                   'updated_at': '2021-10-30T06:30:50+02:00',
                                                   'watchers_count': 1,
                                                   'website': ''},
                                          'repo_id': 1,
                                          'sha': 'f44d122982df2cfe3a5491c0e053ae57df732e59'},
                                 'body': '',
                                 'closed_at': None,
                                 'comments': 0,
                                 'created_at': '2021-10-30T06:44:10+02:00',
                                 'diff_url': 'http://localhost:3000/gitea/demo/pulls/2.diff',
                                 'due_date': None,
                                 'head': {'label': 'bbb',
                                          'ref': 'bbb',
                                          'repo': {'allow_merge_commits': True,
                                                   'allow_rebase': True,
                                                   'allow_rebase_explicit': True,
                                                   'allow_squash_merge': True,
                                                   'archived': False,
                                                   'avatar_url': '',
                                                   'clone_url': 'http://localhost:3000/gitea/demo.git',
                                                   'created_at': '2021-10-27T07:02:38+02:00',
                                                   'default_branch': 'master',
                                                   'default_merge_style': 'merge',
                                                   'description': '',
                                                   'empty': False,
                                                   'fork': False,
                                                   'forks_count': 0,
                                                   'full_name': 'gitea/demo',
                                                   'has_issues': True,
                                                   'has_projects': True,
                                                   'has_pull_requests': True,
                                                   'has_wiki': True,
                                                   'html_url': 'http://localhost:3000/gitea/demo',
                                                   'id': 1,
                                                   'ignore_whitespace_conflicts': False,
                                                   'internal': False,
                                                   'internal_tracker': {'allow_only_contributors_to_track_time': True,
                                                                        'enable_issue_dependencies': True,
                                                                        'enable_time_tracker': True},
                                                   'mirror': False,
                                                   'mirror_interval': '',
                                                   'name': 'demo',
                                                   'open_issues_count': 0,
                                                   'open_pr_counter': 2,
                                                   'original_url': '',
                                                   'owner': {'active': False,
                                                             'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                                             'created': '2021-10-27T07:01:38+02:00',
                                                             'description': '',
                                                             'email': 'godfryd@gmail.com',
                                                             'followers_count': 0,
                                                             'following_count': 0,
                                                             'full_name': '',
                                                             'id': 1,
                                                             'is_admin': False,
                                                             'language': '',
                                                             'last_login': '0001-01-01T00:00:00Z',
                                                             'location': '',
                                                             'login': 'gitea',
                                                             'prohibit_login': False,
                                                             'restricted': False,
                                                             'starred_repos_count': 0,
                                                             'username': 'gitea',
                                                             'visibility': 'public',
                                                             'website': ''},
                                                   'parent': None,
                                                   'permissions': {'admin': False,
                                                                   'pull': True,
                                                                   'push': False},
                                                   'private': False,
                                                   'release_counter': 0,
                                                   'size': 22,
                                                   'ssh_url': 'git@localhost:gitea/demo.git',
                                                   'stars_count': 0,
                                                   'template': False,
                                                   'updated_at': '2021-10-30T06:30:50+02:00',
                                                   'watchers_count': 1,
                                                   'website': ''},
                                          'repo_id': 1,
                                          'sha': 'f9795c3cd6675f5008e93cfcb42d1d8ee4cc582b'},
                                 'html_url': 'http://localhost:3000/gitea/demo/pulls/2',
                                 'id': 2,
                                 'is_locked': False,
                                 'labels': [],
                                 'merge_base': 'f44d122982df2cfe3a5491c0e053ae57df732e59',
                                 'merge_commit_sha': None,
                                 'mergeable': True,
                                 'merged': False,
                                 'merged_at': None,
                                 'merged_by': None,
                                 'milestone': None,
                                 'number': 2,
                                 'patch_url': 'http://localhost:3000/gitea/demo/pulls/2.patch',
                                 'state': 'open',
                                 'title': 'bBb',
                                 'updated_at': '2021-10-30T06:44:10+02:00',
                                 'url': 'http://localhost:3000/gitea/demo/pulls/2',
                                 'user': {'active': False,
                                          'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                          'created': '2021-10-27T07:01:38+02:00',
                                          'description': '',
                                          'email': 'godfryd@gmail.com',
                                          'followers_count': 0,
                                          'following_count': 0,
                                          'full_name': '',
                                          'id': 1,
                                          'is_admin': False,
                                          'language': '',
                                          'last_login': '0001-01-01T00:00:00Z',
                                          'location': '',
                                          'login': 'gitea',
                                          'prohibit_login': False,
                                          'restricted': False,
                                          'starred_repos_count': 0,
                                          'username': 'gitea',
                                          'visibility': 'public',
                                          'website': ''}},
                'repo': 'http://localhost:3000/gitea/demo.git',
                'sender': {'active': False,
                           'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                           'created': '2021-10-27T07:01:38+02:00',
                           'description': '',
                           'email': 'godfryd@gmail.com',
                           'followers_count': 0,
                           'following_count': 0,
                           'full_name': '',
                           'id': 1,
                           'is_admin': False,
                           'language': '',
                           'last_login': '0001-01-01T00:00:00Z',
                           'location': '',
                           'login': 'gitea',
                           'prohibit_login': False,
                           'restricted': False,
                           'starred_repos_count': 0,
                           'username': 'gitea',
                           'visibility': 'public',
                           'website': ''},
                'trigger': 'gitea-pull_request'}

        assert content == ''
        assert code == 204


def test_handle_gitea_webhook_pr_open_with_commits():
    event = 'pull_request'
    signature = 'sha1=bee3adbc045af63569a4b60d448e63cc1e2df292'
    with open('tests/gitea-pr-open-with-commits.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitea_enabled=True, gitea_secret='q6ca2qimhmfauql5qvje'))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitea_webhook(proj.id, payload, event, signature)

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {
                'action': 'opened',
                'after': '8d46acafd2cb71c8136034769176d245167cf543',
                'before': 'f44d122982df2cfe3a5491c0e053ae57df732e59',
                'pull_request': {'assignee': None,
                                 'assignees': None,
                                 'base': {'label': 'master',
                                          'ref': 'master',
                                          'repo': {'allow_merge_commits': True,
                                                   'allow_rebase': True,
                                                   'allow_rebase_explicit': True,
                                                   'allow_squash_merge': True,
                                                   'archived': False,
                                                   'avatar_url': '',
                                                   'clone_url': 'http://localhost:3000/gitea/demo.git',
                                                   'created_at': '2021-10-27T07:02:38+02:00',
                                                   'default_branch': 'master',
                                                   'default_merge_style': 'merge',
                                                   'description': '',
                                                   'empty': False,
                                                   'fork': False,
                                                   'forks_count': 0,
                                                   'full_name': 'gitea/demo',
                                                   'has_issues': True,
                                                   'has_projects': True,
                                                   'has_pull_requests': True,
                                                   'has_wiki': True,
                                                   'html_url': 'http://localhost:3000/gitea/demo',
                                                   'id': 1,
                                                   'ignore_whitespace_conflicts': False,
                                                   'internal': False,
                                                   'internal_tracker': {'allow_only_contributors_to_track_time': True,
                                                                        'enable_issue_dependencies': True,
                                                                        'enable_time_tracker': True},
                                                   'mirror': False,
                                                   'mirror_interval': '',
                                                   'name': 'demo',
                                                   'open_issues_count': 0,
                                                   'open_pr_counter': 2,
                                                   'original_url': '',
                                                   'owner': {'active': False,
                                                             'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                                             'created': '2021-10-27T07:01:38+02:00',
                                                             'description': '',
                                                             'email': 'godfryd@gmail.com',
                                                             'followers_count': 0,
                                                             'following_count': 0,
                                                             'full_name': '',
                                                             'id': 1,
                                                             'is_admin': False,
                                                             'language': '',
                                                             'last_login': '0001-01-01T00:00:00Z',
                                                             'location': '',
                                                             'login': 'gitea',
                                                             'prohibit_login': False,
                                                             'restricted': False,
                                                             'starred_repos_count': 0,
                                                             'username': 'gitea',
                                                             'visibility': 'public',
                                                             'website': ''},
                                                   'parent': None,
                                                   'permissions': {'admin': False,
                                                                   'pull': True,
                                                                   'push': False},
                                                   'private': False,
                                                   'release_counter': 0,
                                                   'size': 22,
                                                   'ssh_url': 'git@localhost:gitea/demo.git',
                                                   'stars_count': 0,
                                                   'template': False,
                                                   'updated_at': '2021-10-30T07:12:21+02:00',
                                                   'watchers_count': 1,
                                                   'website': ''},
                                          'repo_id': 1,
                                          'sha': 'f44d122982df2cfe3a5491c0e053ae57df732e59'},
                                 'body': '',
                                 'closed_at': None,
                                 'comments': 0,
                                 'created_at': '2021-10-30T07:26:28+02:00',
                                 'diff_url': 'http://localhost:3000/gitea/demo/pulls/3.diff',
                                 'due_date': None,
                                 'head': {'label': 'ccc',
                                          'ref': 'ccc',
                                          'repo': {'allow_merge_commits': True,
                                                   'allow_rebase': True,
                                                   'allow_rebase_explicit': True,
                                                   'allow_squash_merge': True,
                                                   'archived': False,
                                                   'avatar_url': '',
                                                   'clone_url': 'http://localhost:3000/gitea/demo.git',
                                                   'created_at': '2021-10-27T07:02:38+02:00',
                                                   'default_branch': 'master',
                                                   'default_merge_style': 'merge',
                                                   'description': '',
                                                   'empty': False,
                                                   'fork': False,
                                                   'forks_count': 0,
                                                   'full_name': 'gitea/demo',
                                                   'has_issues': True,
                                                   'has_projects': True,
                                                   'has_pull_requests': True,
                                                   'has_wiki': True,
                                                   'html_url': 'http://localhost:3000/gitea/demo',
                                                   'id': 1,
                                                   'ignore_whitespace_conflicts': False,
                                                   'internal': False,
                                                   'internal_tracker': {'allow_only_contributors_to_track_time': True,
                                                                        'enable_issue_dependencies': True,
                                                                        'enable_time_tracker': True},
                                                   'mirror': False,
                                                   'mirror_interval': '',
                                                   'name': 'demo',
                                                   'open_issues_count': 0,
                                                   'open_pr_counter': 2,
                                                   'original_url': '',
                                                   'owner': {'active': False,
                                                             'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                                             'created': '2021-10-27T07:01:38+02:00',
                                                             'description': '',
                                                             'email': 'godfryd@gmail.com',
                                                             'followers_count': 0,
                                                             'following_count': 0,
                                                             'full_name': '',
                                                             'id': 1,
                                                             'is_admin': False,
                                                             'language': '',
                                                             'last_login': '0001-01-01T00:00:00Z',
                                                             'location': '',
                                                             'login': 'gitea',
                                                             'prohibit_login': False,
                                                             'restricted': False,
                                                             'starred_repos_count': 0,
                                                             'username': 'gitea',
                                                             'visibility': 'public',
                                                             'website': ''},
                                                   'parent': None,
                                                   'permissions': {'admin': False,
                                                                   'pull': True,
                                                                   'push': False},
                                                   'private': False,
                                                   'release_counter': 0,
                                                   'size': 22,
                                                   'ssh_url': 'git@localhost:gitea/demo.git',
                                                   'stars_count': 0,
                                                   'template': False,
                                                   'updated_at': '2021-10-30T07:12:21+02:00',
                                                   'watchers_count': 1,
                                                   'website': ''},
                                          'repo_id': 1,
                                          'sha': '8d46acafd2cb71c8136034769176d245167cf543'},
                                 'html_url': 'http://localhost:3000/gitea/demo/pulls/3',
                                 'id': 3,
                                 'is_locked': False,
                                 'labels': [],
                                 'merge_base': 'f44d122982df2cfe3a5491c0e053ae57df732e59',
                                 'merge_commit_sha': None,
                                 'mergeable': True,
                                 'merged': False,
                                 'merged_at': None,
                                 'merged_by': None,
                                 'milestone': None,
                                 'number': 3,
                                 'patch_url': 'http://localhost:3000/gitea/demo/pulls/3.patch',
                                 'state': 'open',
                                 'title': 'cCc',
                                 'updated_at': '2021-10-30T07:26:28+02:00',
                                 'url': 'http://localhost:3000/gitea/demo/pulls/3',
                                 'user': {'active': False,
                                          'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                                          'created': '2021-10-27T07:01:38+02:00',
                                          'description': '',
                                          'email': 'godfryd@gmail.com',
                                          'followers_count': 0,
                                          'following_count': 0,
                                          'full_name': '',
                                          'id': 1,
                                          'is_admin': False,
                                          'language': '',
                                          'last_login': '0001-01-01T00:00:00Z',
                                          'location': '',
                                          'login': 'gitea',
                                          'prohibit_login': False,
                                          'restricted': False,
                                          'starred_repos_count': 0,
                                          'username': 'gitea',
                                          'visibility': 'public',
                                          'website': ''}},
                'repo': 'http://localhost:3000/gitea/demo.git',
                'sender': {'active': False,
                           'avatar_url': 'http://localhost:3000/user/avatar/gitea/-1',
                           'created': '2021-10-27T07:01:38+02:00',
                           'description': '',
                           'email': 'godfryd@gmail.com',
                           'followers_count': 0,
                           'following_count': 0,
                           'full_name': '',
                           'id': 1,
                           'is_admin': False,
                           'language': '',
                           'last_login': '0001-01-01T00:00:00Z',
                           'location': '',
                           'login': 'gitea',
                           'prohibit_login': False,
                           'restricted': False,
                           'starred_repos_count': 0,
                           'username': 'gitea',
                           'visibility': 'public',
                           'website': ''},
                'trigger': 'gitea-pull_request'}


        assert content == ''
        assert code == 204


def test_handle_gitlab_webhook_push():
    event = 'Push Hook'
    token = 'm10h7p3shc9a79gvynta'
    with open('tests/gitlab-push.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitlab_enabled=True, gitlab_secret=token))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitlab_webhook(proj.id, payload, event, token)

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {
                'after': '2b4354ca632e5d517f8d35a3f26512d6bc4695e2',
                'before': '15666b2895433cdf76f4b5823accf66675ef78dd',
                'commits': [{'added': [],
                             'author': {'email': 'godfryd@gmail.com',
                                        'name': 'Michal Nowikowski'},
                             'id': '2b4354ca632e5d517f8d35a3f26512d6bc4695e2',
                             'message': 'updated\n',
                             'modified': ['README.md'],
                             'removed': [],
                             'timestamp': '2021-10-31T07:07:36+01:00',
                             'title': 'updated',
                             'url': 'http://gitlab.example.com/root/kraken-demo/-/commit/2b4354ca632e5d517f8d35a3f26512d6bc4695e2'}],
                'pusher': {'email': '', 'full_name': 'Administrator', 'username': 'root'},
                'ref': 'refs/heads/main',
                'repo': 'http://gitlab.example.com/root/kraken-demo.git',
                'trigger': 'gitlab-Push Hook'}

        assert content == ''
        assert code == 204


def test_handle_gitlab_webhook_mr_update():
    event = 'Merge Request Hook'
    token = 'm10h7p3shc9a79gvynta'
    with open('tests/gitlab-mr-update.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitlab_enabled=True, gitlab_secret=token))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitlab_webhook(proj.id, payload, event, token)

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {
                'action': 'update',
                'after': 'bf3bde7a2eedd0ebd638b6cbca5b718eea8ad186',
                'before': '5637be2bb815fb5f30f0e492055a797909ce41a9',
                'pull_request': {'head': {'ref': 'aaa'},
                                 'base': {'ref': 'main',
                                          'sha': '5637be2bb815fb5f30f0e492055a797909ce41a9'},
                                 'user': {'login': 'root',
                                          'html_url': 'http://gitlab.example.com/root'},
                                 'html_url': 'http://gitlab.example.com/root/kraken-demo/-/merge_requests/1',
                                 'number': 1,
                                 'title': 'Draft: Aaa',
                                 'updated_at': '2021-11-01T05:48:06+00:00'},
                'repo': 'http://gitlab.example.com/root/kraken-demo.git',
                'sender': {'avatar_url': 'https://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=80&d=identicon',
                           'email': '[REDACTED]',
                           'id': 1,
                           'name': 'Administrator',
                           'username': 'root'},
                'trigger': 'gitlab-Merge Request Hook'}

        assert content == ''
        assert code == 204


def test_handle_gitlab_webhook_mr_open():
    event = 'Merge Request Hook'
    token = 'm10h7p3shc9a79gvynta'
    with open('tests/gitlab-mr-open.json', 'rb') as f:
        payload = f.read()

    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj', webhooks=dict(gitlab_enabled=True, gitlab_secret=token))
        db.session.commit()

        # check handling the request
        with patch('kraken.server.kkrq.enq') as ke:
            content, code = webhooks._handle_gitlab_webhook(proj.id, payload, event, token)

            ke.assert_called_once()
            assert ke.call_args[0][0] == bg_jobs.trigger_flow
            assert ke.call_args[0][1] == proj.id
            assert ke.call_args[0][2] == {
                'action': 'open',
                'after': '204c5e311bafae0124a1ef98bfa5c5ea758242ae',
                'before': '',
                'pull_request': {'head': {'ref': 'bbb'},
                                 'base': {'ref': 'main', 'sha': ''},
                                 'user': {'login': 'root',
                                          'html_url': 'http://gitlab.example.com/root'},
                                 'html_url': 'http://gitlab.example.com/root/kraken-demo/-/merge_requests/2',
                                 'number': 2,
                                 'title': 'Bbb',
                                 'updated_at': '2021-11-01T06:15:26+00:00'},
                'repo': 'http://gitlab.example.com/root/kraken-demo.git',
                'sender': {'avatar_url': 'https://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=80&d=identicon',
                           'email': '[REDACTED]',
                           'id': 1,
                           'name': 'Administrator',
                           'username': 'root'},
                'trigger': 'gitlab-Merge Request Hook'}

        assert content == ''
        assert code == 204
