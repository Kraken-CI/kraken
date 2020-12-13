#!/usr/bin/env python3

import json
import urllib.request


def do_push():
    payload = {
      "ref": "refs/heads/master",
      "before": "c172e165cd0982046b3578afe2b01efa901f5b4f",
      "after": "6ce92756d435d9a73171ea935572b71b82d0c141",
      "repository": {
        "id": 280832057,
        "node_id": "MDEwOlJlcG9zaXRvcnkyODA4MzIwNTc=",
        "name": "kraken",
        "full_name": "Kraken-CI/kraken",
        "private": False,
        "owner": {
          "name": "Kraken-CI",
          "email": None,
          "login": "Kraken-CI",
          "id": 68497961,
          "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
          "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
          "gravatar_id": "",
          "url": "https://api.github.com/users/Kraken-CI",
          "html_url": "https://github.com/Kraken-CI",
          "followers_url": "https://api.github.com/users/Kraken-CI/followers",
          "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
          "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
          "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
          "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
          "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
          "repos_url": "https://api.github.com/users/Kraken-CI/repos",
          "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
          "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
          "type": "Organization",
          "site_admin": False
        },
        "html_url": "https://github.com/Kraken-CI/kraken",
        "description": "Kraken CI is a continuous integration and testing system.",
        "fork": False,
        "url": "https://github.com/Kraken-CI/kraken",
        "forks_url": "https://api.github.com/repos/Kraken-CI/kraken/forks",
        "keys_url": "https://api.github.com/repos/Kraken-CI/kraken/keys{/key_id}",
        "collaborators_url": "https://api.github.com/repos/Kraken-CI/kraken/collaborators{/collaborator}",
        "teams_url": "https://api.github.com/repos/Kraken-CI/kraken/teams",
        "hooks_url": "https://api.github.com/repos/Kraken-CI/kraken/hooks",
        "issue_events_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/events{/number}",
        "events_url": "https://api.github.com/repos/Kraken-CI/kraken/events",
        "assignees_url": "https://api.github.com/repos/Kraken-CI/kraken/assignees{/user}",
        "branches_url": "https://api.github.com/repos/Kraken-CI/kraken/branches{/branch}",
        "tags_url": "https://api.github.com/repos/Kraken-CI/kraken/tags",
        "blobs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/blobs{/sha}",
        "git_tags_url": "https://api.github.com/repos/Kraken-CI/kraken/git/tags{/sha}",
        "git_refs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/refs{/sha}",
        "trees_url": "https://api.github.com/repos/Kraken-CI/kraken/git/trees{/sha}",
        "statuses_url": "https://api.github.com/repos/Kraken-CI/kraken/statuses/{sha}",
        "languages_url": "https://api.github.com/repos/Kraken-CI/kraken/languages",
        "stargazers_url": "https://api.github.com/repos/Kraken-CI/kraken/stargazers",
        "contributors_url": "https://api.github.com/repos/Kraken-CI/kraken/contributors",
        "subscribers_url": "https://api.github.com/repos/Kraken-CI/kraken/subscribers",
        "subscription_url": "https://api.github.com/repos/Kraken-CI/kraken/subscription",
        "commits_url": "https://api.github.com/repos/Kraken-CI/kraken/commits{/sha}",
        "git_commits_url": "https://api.github.com/repos/Kraken-CI/kraken/git/commits{/sha}",
        "comments_url": "https://api.github.com/repos/Kraken-CI/kraken/comments{/number}",
        "issue_comment_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/comments{/number}",
        "contents_url": "https://api.github.com/repos/Kraken-CI/kraken/contents/{+path}",
        "compare_url": "https://api.github.com/repos/Kraken-CI/kraken/compare/{base}...{head}",
        "merges_url": "https://api.github.com/repos/Kraken-CI/kraken/merges",
        "archive_url": "https://api.github.com/repos/Kraken-CI/kraken/{archive_format}{/ref}",
        "downloads_url": "https://api.github.com/repos/Kraken-CI/kraken/downloads",
        "issues_url": "https://api.github.com/repos/Kraken-CI/kraken/issues{/number}",
        "pulls_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls{/number}",
        "milestones_url": "https://api.github.com/repos/Kraken-CI/kraken/milestones{/number}",
        "notifications_url": "https://api.github.com/repos/Kraken-CI/kraken/notifications{?since,all,participating}",
        "labels_url": "https://api.github.com/repos/Kraken-CI/kraken/labels{/name}",
        "releases_url": "https://api.github.com/repos/Kraken-CI/kraken/releases{/id}",
        "deployments_url": "https://api.github.com/repos/Kraken-CI/kraken/deployments",
        "created_at": 1595150557,
        "updated_at": "2020-12-11T05:56:50Z",
        "pushed_at": 1607691099,
        "git_url": "git://github.com/Kraken-CI/kraken.git",
        "ssh_url": "git@github.com:Kraken-CI/kraken.git",
        "clone_url": "https://github.com/Kraken-CI/kraken.git",
        "svn_url": "https://github.com/Kraken-CI/kraken",
        "homepage": "https://kraken.ci/",
        "size": 1189,
        "stargazers_count": 3,
        "watchers_count": 3,
        "language": "Python",
        "has_issues": True,
        "has_projects": True,
        "has_downloads": True,
        "has_wiki": True,
        "has_pages": False,
        "forks_count": 0,
        "mirror_url": None,
        "archived": False,
        "disabled": False,
        "open_issues_count": 32,
        "license": {
          "key": "apache-2.0",
          "name": "Apache License 2.0",
          "spdx_id": "Apache-2.0",
          "url": "https://api.github.com/licenses/apache-2.0",
          "node_id": "MDc6TGljZW5zZTI="
        },
        "forks": 0,
        "open_issues": 32,
        "watchers": 3,
        "default_branch": "master",
        "stargazers": 3,
        "master_branch": "master",
        "organization": "Kraken-CI"
      },
      "pusher": {
        "name": "godfryd",
        "email": "godfryd@gmail.com"
      },
      "organization": {
        "login": "Kraken-CI",
        "id": 68497961,
        "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
        "url": "https://api.github.com/orgs/Kraken-CI",
        "repos_url": "https://api.github.com/orgs/Kraken-CI/repos",
        "events_url": "https://api.github.com/orgs/Kraken-CI/events",
        "hooks_url": "https://api.github.com/orgs/Kraken-CI/hooks",
        "issues_url": "https://api.github.com/orgs/Kraken-CI/issues",
        "members_url": "https://api.github.com/orgs/Kraken-CI/members{/member}",
        "public_members_url": "https://api.github.com/orgs/Kraken-CI/public_members{/member}",
        "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
        "description": None
      },
      "sender": {
        "login": "godfryd",
        "id": 176567,
        "node_id": "MDQ6VXNlcjE3NjU2Nw==",
        "avatar_url": "https://avatars1.githubusercontent.com/u/176567?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/godfryd",
        "html_url": "https://github.com/godfryd",
        "followers_url": "https://api.github.com/users/godfryd/followers",
        "following_url": "https://api.github.com/users/godfryd/following{/other_user}",
        "gists_url": "https://api.github.com/users/godfryd/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/godfryd/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/godfryd/subscriptions",
        "organizations_url": "https://api.github.com/users/godfryd/orgs",
        "repos_url": "https://api.github.com/users/godfryd/repos",
        "events_url": "https://api.github.com/users/godfryd/events{/privacy}",
        "received_events_url": "https://api.github.com/users/godfryd/received_events",
        "type": "User",
        "site_admin": False
      },
      "created": False,
      "deleted": False,
      "forced": False,
      "base_ref": None,
      "compare": "https://github.com/Kraken-CI/kraken/compare/c172e165cd09...6ce92756d435",
      "commits": [
        {
          "id": "4b264a8beb10d8086c4c8540b614e633d9957d75",
          "tree_id": "74ba51832f9e203bbaf19292ac8479f4db9e5222",
          "distinct": True,
          "message": "added line numbering in job log on run-results page",
          "timestamp": "2020-12-11T13:51:37+01:00",
          "url": "https://github.com/Kraken-CI/kraken/commit/4b264a8beb10d8086c4c8540b614e633d9957d75",
          "author": {
            "name": "Michal Nowikowski",
            "email": "godfryd@gmail.com",
            "username": "godfryd"
          },
          "committer": {
            "name": "Michal Nowikowski",
            "email": "godfryd@gmail.com",
            "username": "godfryd"
          },
          "added": [

          ],
          "removed": [

          ],
          "modified": [
            "ui/src/app/log-box/log-box.component.html",
            "ui/src/app/log-box/log-box.component.ts"
          ]
        },
        {
          "id": "6ce92756d435d9a73171ea935572b71b82d0c141",
          "tree_id": "c76a9f82e471d7234868ff62105cbdec4a6894c5",
          "distinct": True,
          "message": "added paging logs backward and forward",
          "timestamp": "2020-12-11T13:51:37+01:00",
          "url": "https://github.com/Kraken-CI/kraken/commit/6ce92756d435d9a73171ea935572b71b82d0c141",
          "author": {
            "name": "Michal Nowikowski",
            "email": "godfryd@gmail.com",
            "username": "godfryd"
          },
          "committer": {
            "name": "Michal Nowikowski",
            "email": "godfryd@gmail.com",
            "username": "godfryd"
          },
          "added": [

          ],
          "removed": [

          ],
          "modified": [
            "server/kraken/server/execution.py",
            "ui/src/app/log-box/log-box.component.html",
            "ui/src/app/log-box/log-box.component.ts"
          ]
        }
      ],
      "head_commit": {
        "id": "6ce92756d435d9a73171ea935572b71b82d0c141",
        "tree_id": "c76a9f82e471d7234868ff62105cbdec4a6894c5",
        "distinct": True,
        "message": "added paging logs backward and forward",
        "timestamp": "2020-12-11T13:51:37+01:00",
        "url": "https://github.com/Kraken-CI/kraken/commit/6ce92756d435d9a73171ea935572b71b82d0c141",
        "author": {
          "name": "Michal Nowikowski",
          "email": "godfryd@gmail.com",
          "username": "godfryd"
        },
        "committer": {
          "name": "Michal Nowikowski",
          "email": "godfryd@gmail.com",
          "username": "godfryd"
        },

        "added": [

        ],
        "removed": [

        ],
        "modified": [
          "server/kraken/server/execution.py",
          "ui/src/app/log-box/log-box.component.html",
          "ui/src/app/log-box/log-box.component.ts"
        ]
      }
    }

    data = json.dumps(payload)

    req = urllib.request.Request("http://localhost:8080/webhooks/2/github", data.encode('utf-8'))

    req.add_header('X-GitHub-Event', 'push')
    req.add_header('X-Hub-Signature', 'sha1=a8074cb2a006aefd9363396c0391b068b0e5f320')

    with urllib.request.urlopen(req) as f:
        print(f.read())


def do_pull_request():
    payload = {
        "action": "synchronize",
          "number": 59,
          "pull_request": {
            "url": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59",
            "id": 535420203,
            "node_id": "MDExOlB1bGxSZXF1ZXN0NTM1NDIwMjAz",
            "html_url": "https://github.com/Kraken-CI/kraken/pull/59",
            "diff_url": "https://github.com/Kraken-CI/kraken/pull/59.diff",
            "patch_url": "https://github.com/Kraken-CI/kraken/pull/59.patch",
            "issue_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/59",
            "number": 59,
            "state": "open",
            "locked": False,
            "title": "[#42] initial commit to branch",
            "user": {
              "login": "godfryd",
              "id": 176567,
              "node_id": "MDQ6VXNlcjE3NjU2Nw==",
              "avatar_url": "https://avatars1.githubusercontent.com/u/176567?v=4",
              "gravatar_id": "",
              "url": "https://api.github.com/users/godfryd",
              "html_url": "https://github.com/godfryd",
              "followers_url": "https://api.github.com/users/godfryd/followers",
              "following_url": "https://api.github.com/users/godfryd/following{/other_user}",
              "gists_url": "https://api.github.com/users/godfryd/gists{/gist_id}",
              "starred_url": "https://api.github.com/users/godfryd/starred{/owner}{/repo}",
              "subscriptions_url": "https://api.github.com/users/godfryd/subscriptions",
              "organizations_url": "https://api.github.com/users/godfryd/orgs",
              "repos_url": "https://api.github.com/users/godfryd/repos",
              "events_url": "https://api.github.com/users/godfryd/events{/privacy}",
              "received_events_url": "https://api.github.com/users/godfryd/received_events",
              "type": "User",
              "site_admin": False
            },
            "body": "",
            "created_at": "2020-12-09T19:42:17Z",
            "updated_at": "2020-12-09T19:47:00Z",
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": "fd1399eb61bbf4629f4d251504f0db1d3bc5619a",
            "assignee": None,
            "assignees": [

            ],
            "requested_reviewers": [

            ],
            "requested_teams": [

            ],
            "labels": [

            ],
            "milestone": None,
            "draft": False,
            "commits_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59/commits",
            "review_comments_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59/comments",
            "review_comment_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls/comments{/number}",
            "comments_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/59/comments",
            "statuses_url": "https://api.github.com/repos/Kraken-CI/kraken/statuses/fae03cba55c93f6da39ad66401ee1241d54b2c6c",
            "head": {
              "label": "Kraken-CI:gh-pr-support",
              "ref": "gh-pr-support",
              "sha": "fae03cba55c93f6da39ad66401ee1241d54b2c6c",
              "user": {
                "login": "Kraken-CI",
                "id": 68497961,
                "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
                "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/Kraken-CI",
                "html_url": "https://github.com/Kraken-CI",
                "followers_url": "https://api.github.com/users/Kraken-CI/followers",
                "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
                "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
                "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
                "repos_url": "https://api.github.com/users/Kraken-CI/repos",
                "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
                "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
                "type": "Organization",
                "site_admin": False
              },
              "repo": {
                "id": 280832057,
                "node_id": "MDEwOlJlcG9zaXRvcnkyODA4MzIwNTc=",
                "name": "kraken",
                "full_name": "Kraken-CI/kraken",
                "private": False,
                "owner": {
                  "login": "Kraken-CI",
                  "id": 68497961,
                  "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
                  "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
                  "gravatar_id": "",
                  "url": "https://api.github.com/users/Kraken-CI",
                  "html_url": "https://github.com/Kraken-CI",
                  "followers_url": "https://api.github.com/users/Kraken-CI/followers",
                  "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
                  "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
                  "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
                  "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
                  "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
                  "repos_url": "https://api.github.com/users/Kraken-CI/repos",
                  "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
                  "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
                  "type": "Organization",
                  "site_admin": False
                },
                "html_url": "https://github.com/Kraken-CI/kraken",
                "description": "Kraken CI is a continuous integration and testing system.",
                "fork": False,
                "url": "https://api.github.com/repos/Kraken-CI/kraken",
                "forks_url": "https://api.github.com/repos/Kraken-CI/kraken/forks",
                "keys_url": "https://api.github.com/repos/Kraken-CI/kraken/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/Kraken-CI/kraken/collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/Kraken-CI/kraken/teams",
                "hooks_url": "https://api.github.com/repos/Kraken-CI/kraken/hooks",
                "issue_events_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/events{/number}",
                "events_url": "https://api.github.com/repos/Kraken-CI/kraken/events",
                "assignees_url": "https://api.github.com/repos/Kraken-CI/kraken/assignees{/user}",
                "branches_url": "https://api.github.com/repos/Kraken-CI/kraken/branches{/branch}",
                "tags_url": "https://api.github.com/repos/Kraken-CI/kraken/tags",
                "blobs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/Kraken-CI/kraken/git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/Kraken-CI/kraken/git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/Kraken-CI/kraken/statuses/{sha}",
                "languages_url": "https://api.github.com/repos/Kraken-CI/kraken/languages",
                "stargazers_url": "https://api.github.com/repos/Kraken-CI/kraken/stargazers",
                "contributors_url": "https://api.github.com/repos/Kraken-CI/kraken/contributors",
                "subscribers_url": "https://api.github.com/repos/Kraken-CI/kraken/subscribers",
                "subscription_url": "https://api.github.com/repos/Kraken-CI/kraken/subscription",
                "commits_url": "https://api.github.com/repos/Kraken-CI/kraken/commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/Kraken-CI/kraken/git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/Kraken-CI/kraken/comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/Kraken-CI/kraken/contents/{+path}",
                "compare_url": "https://api.github.com/repos/Kraken-CI/kraken/compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/Kraken-CI/kraken/merges",
                "archive_url": "https://api.github.com/repos/Kraken-CI/kraken/{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/Kraken-CI/kraken/downloads",
                "issues_url": "https://api.github.com/repos/Kraken-CI/kraken/issues{/number}",
                "pulls_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls{/number}",
                "milestones_url": "https://api.github.com/repos/Kraken-CI/kraken/milestones{/number}",
                "notifications_url": "https://api.github.com/repos/Kraken-CI/kraken/notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/Kraken-CI/kraken/labels{/name}",
                "releases_url": "https://api.github.com/repos/Kraken-CI/kraken/releases{/id}",
                "deployments_url": "https://api.github.com/repos/Kraken-CI/kraken/deployments",
                "created_at": "2020-07-19T09:22:37Z",
                "updated_at": "2020-12-09T18:54:32Z",
                "pushed_at": "2020-12-09T19:47:00Z",
                "git_url": "git://github.com/Kraken-CI/kraken.git",
                "ssh_url": "git@github.com:Kraken-CI/kraken.git",
                "clone_url": "https://github.com/Kraken-CI/kraken.git",
                "svn_url": "https://github.com/Kraken-CI/kraken",
                "homepage": "https://kraken.ci/",
                "size": 1134,
                "stargazers_count": 3,
                "watchers_count": 3,
                "language": "Python",
                "has_issues": True,
                "has_projects": True,
                "has_downloads": True,
                "has_wiki": True,
                "has_pages": False,
                "forks_count": 0,
                "mirror_url": None,
                "archived": False,
                "disabled": False,
                "open_issues_count": 30,
                "license": {
                  "key": "apache-2.0",
                  "name": "Apache License 2.0",
                  "spdx_id": "Apache-2.0",
                  "url": "https://api.github.com/licenses/apache-2.0",
                  "node_id": "MDc6TGljZW5zZTI="
                },
                "forks": 0,
                "open_issues": 30,
                "watchers": 3,
                "default_branch": "master",
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": True,
                "delete_branch_on_merge": False
              }
            },
            "base": {
              "label": "Kraken-CI:master",
              "ref": "master",
              "sha": "c5b2254bea37f512b62e0914cd1a9e8e9aa7dfcc",
              "user": {
                "login": "Kraken-CI",
                "id": 68497961,
                "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
                "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/Kraken-CI",
                "html_url": "https://github.com/Kraken-CI",
                "followers_url": "https://api.github.com/users/Kraken-CI/followers",
                "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
                "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
                "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
                "repos_url": "https://api.github.com/users/Kraken-CI/repos",
                "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
                "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
                "type": "Organization",
                "site_admin": False
              },
              "repo": {
                "id": 280832057,
                "node_id": "MDEwOlJlcG9zaXRvcnkyODA4MzIwNTc=",
                "name": "kraken",
                "full_name": "Kraken-CI/kraken",
                "private": False,
                "owner": {
                  "login": "Kraken-CI",
                  "id": 68497961,
                  "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
                  "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
                  "gravatar_id": "",
                  "url": "https://api.github.com/users/Kraken-CI",
                  "html_url": "https://github.com/Kraken-CI",
                  "followers_url": "https://api.github.com/users/Kraken-CI/followers",
                  "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
                  "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
                  "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
                  "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
                  "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
                  "repos_url": "https://api.github.com/users/Kraken-CI/repos",
                  "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
                  "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
                  "type": "Organization",
                  "site_admin": False
                },
                "html_url": "https://github.com/Kraken-CI/kraken",
                "description": "Kraken CI is a continuous integration and testing system.",
                "fork": False,
                "url": "https://api.github.com/repos/Kraken-CI/kraken",
                "forks_url": "https://api.github.com/repos/Kraken-CI/kraken/forks",
                "keys_url": "https://api.github.com/repos/Kraken-CI/kraken/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/Kraken-CI/kraken/collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/Kraken-CI/kraken/teams",
                "hooks_url": "https://api.github.com/repos/Kraken-CI/kraken/hooks",
                "issue_events_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/events{/number}",
                "events_url": "https://api.github.com/repos/Kraken-CI/kraken/events",
                "assignees_url": "https://api.github.com/repos/Kraken-CI/kraken/assignees{/user}",
                "branches_url": "https://api.github.com/repos/Kraken-CI/kraken/branches{/branch}",
                "tags_url": "https://api.github.com/repos/Kraken-CI/kraken/tags",
                "blobs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/Kraken-CI/kraken/git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/Kraken-CI/kraken/git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/Kraken-CI/kraken/statuses/{sha}",
                "languages_url": "https://api.github.com/repos/Kraken-CI/kraken/languages",
                "stargazers_url": "https://api.github.com/repos/Kraken-CI/kraken/stargazers",
                "contributors_url": "https://api.github.com/repos/Kraken-CI/kraken/contributors",
                "subscribers_url": "https://api.github.com/repos/Kraken-CI/kraken/subscribers",
                "subscription_url": "https://api.github.com/repos/Kraken-CI/kraken/subscription",
                "commits_url": "https://api.github.com/repos/Kraken-CI/kraken/commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/Kraken-CI/kraken/git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/Kraken-CI/kraken/comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/Kraken-CI/kraken/contents/{+path}",
                "compare_url": "https://api.github.com/repos/Kraken-CI/kraken/compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/Kraken-CI/kraken/merges",
                "archive_url": "https://api.github.com/repos/Kraken-CI/kraken/{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/Kraken-CI/kraken/downloads",
                "issues_url": "https://api.github.com/repos/Kraken-CI/kraken/issues{/number}",
                "pulls_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls{/number}",
                "milestones_url": "https://api.github.com/repos/Kraken-CI/kraken/milestones{/number}",
                "notifications_url": "https://api.github.com/repos/Kraken-CI/kraken/notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/Kraken-CI/kraken/labels{/name}",
                "releases_url": "https://api.github.com/repos/Kraken-CI/kraken/releases{/id}",
                "deployments_url": "https://api.github.com/repos/Kraken-CI/kraken/deployments",
                "created_at": "2020-07-19T09:22:37Z",
                "updated_at": "2020-12-09T18:54:32Z",
                "pushed_at": "2020-12-09T19:47:00Z",
                "git_url": "git://github.com/Kraken-CI/kraken.git",
                "ssh_url": "git@github.com:Kraken-CI/kraken.git",
                "clone_url": "https://github.com/Kraken-CI/kraken.git",
                "svn_url": "https://github.com/Kraken-CI/kraken",
                "homepage": "https://kraken.ci/",
                "size": 1134,
                "stargazers_count": 3,
                "watchers_count": 3,
                "language": "Python",
                "has_issues": True,
                "has_projects": True,
                "has_downloads": True,
                "has_wiki": True,
                "has_pages": False,
                "forks_count": 0,
                "mirror_url": None,
                "archived": False,
                "disabled": False,
                "open_issues_count": 30,
                "license": {
                  "key": "apache-2.0",
                  "name": "Apache License 2.0",
                  "spdx_id": "Apache-2.0",
                  "url": "https://api.github.com/licenses/apache-2.0",
                  "node_id": "MDc6TGljZW5zZTI="
                },
                "forks": 0,
                "open_issues": 30,
                "watchers": 3,
                "default_branch": "master",
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": True,
                "delete_branch_on_merge": False
              }
            },
            "_links": {
              "self": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59"
              },
              "html": {
                "href": "https://github.com/Kraken-CI/kraken/pull/59"
              },
              "issue": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/issues/59"
              },
              "comments": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/issues/59/comments"
              },
              "review_comments": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59/comments"
              },
              "review_comment": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/pulls/comments{/number}"
              },
              "commits": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/pulls/59/commits"
              },
              "statuses": {
                "href": "https://api.github.com/repos/Kraken-CI/kraken/statuses/fae03cba55c93f6da39ad66401ee1241d54b2c6c"
              }
            },
            "author_association": "CONTRIBUTOR",
            "active_lock_reason": None,
            "merged": False,
            "mergeable": None,
            "rebaseable": None,
            "mergeable_state": "unknown",
            "merged_by": None,
            "comments": 0,
            "review_comments": 0,
            "maintainer_can_modify": False,
            "commits": 3,
            "additions": 1,
            "deletions": 0,
            "changed_files": 1
          },
          "before": "a71b2d6bcb5be8a96bbdecd09438385080f18a1c",
          "after": "fae03cba55c93f6da39ad66401ee1241d54b2c6c",
          "repository": {
            "id": 280832057,
            "node_id": "MDEwOlJlcG9zaXRvcnkyODA4MzIwNTc=",
            "name": "kraken",
            "full_name": "Kraken-CI/kraken",
            "private": False,
            "owner": {
              "login": "Kraken-CI",
              "id": 68497961,
              "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
              "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
              "gravatar_id": "",
              "url": "https://api.github.com/users/Kraken-CI",
              "html_url": "https://github.com/Kraken-CI",
              "followers_url": "https://api.github.com/users/Kraken-CI/followers",
              "following_url": "https://api.github.com/users/Kraken-CI/following{/other_user}",
              "gists_url": "https://api.github.com/users/Kraken-CI/gists{/gist_id}",
              "starred_url": "https://api.github.com/users/Kraken-CI/starred{/owner}{/repo}",
              "subscriptions_url": "https://api.github.com/users/Kraken-CI/subscriptions",
              "organizations_url": "https://api.github.com/users/Kraken-CI/orgs",
              "repos_url": "https://api.github.com/users/Kraken-CI/repos",
              "events_url": "https://api.github.com/users/Kraken-CI/events{/privacy}",
              "received_events_url": "https://api.github.com/users/Kraken-CI/received_events",
              "type": "Organization",
              "site_admin": False
            },
            "html_url": "https://github.com/Kraken-CI/kraken",
            "description": "Kraken CI is a continuous integration and testing system.",
            "fork": False,
            "url": "https://api.github.com/repos/Kraken-CI/kraken",
            "forks_url": "https://api.github.com/repos/Kraken-CI/kraken/forks",
            "keys_url": "https://api.github.com/repos/Kraken-CI/kraken/keys{/key_id}",
            "collaborators_url": "https://api.github.com/repos/Kraken-CI/kraken/collaborators{/collaborator}",
            "teams_url": "https://api.github.com/repos/Kraken-CI/kraken/teams",
            "hooks_url": "https://api.github.com/repos/Kraken-CI/kraken/hooks",
            "issue_events_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/events{/number}",
            "events_url": "https://api.github.com/repos/Kraken-CI/kraken/events",
            "assignees_url": "https://api.github.com/repos/Kraken-CI/kraken/assignees{/user}",
            "branches_url": "https://api.github.com/repos/Kraken-CI/kraken/branches{/branch}",
            "tags_url": "https://api.github.com/repos/Kraken-CI/kraken/tags",
            "blobs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/blobs{/sha}",
            "git_tags_url": "https://api.github.com/repos/Kraken-CI/kraken/git/tags{/sha}",
            "git_refs_url": "https://api.github.com/repos/Kraken-CI/kraken/git/refs{/sha}",
            "trees_url": "https://api.github.com/repos/Kraken-CI/kraken/git/trees{/sha}",
            "statuses_url": "https://api.github.com/repos/Kraken-CI/kraken/statuses/{sha}",
            "languages_url": "https://api.github.com/repos/Kraken-CI/kraken/languages",
            "stargazers_url": "https://api.github.com/repos/Kraken-CI/kraken/stargazers",
            "contributors_url": "https://api.github.com/repos/Kraken-CI/kraken/contributors",
            "subscribers_url": "https://api.github.com/repos/Kraken-CI/kraken/subscribers",
            "subscription_url": "https://api.github.com/repos/Kraken-CI/kraken/subscription",
            "commits_url": "https://api.github.com/repos/Kraken-CI/kraken/commits{/sha}",
            "git_commits_url": "https://api.github.com/repos/Kraken-CI/kraken/git/commits{/sha}",
            "comments_url": "https://api.github.com/repos/Kraken-CI/kraken/comments{/number}",
            "issue_comment_url": "https://api.github.com/repos/Kraken-CI/kraken/issues/comments{/number}",
            "contents_url": "https://api.github.com/repos/Kraken-CI/kraken/contents/{+path}",
            "compare_url": "https://api.github.com/repos/Kraken-CI/kraken/compare/{base}...{head}",
            "merges_url": "https://api.github.com/repos/Kraken-CI/kraken/merges",
            "archive_url": "https://api.github.com/repos/Kraken-CI/kraken/{archive_format}{/ref}",
            "downloads_url": "https://api.github.com/repos/Kraken-CI/kraken/downloads",
            "issues_url": "https://api.github.com/repos/Kraken-CI/kraken/issues{/number}",
            "pulls_url": "https://api.github.com/repos/Kraken-CI/kraken/pulls{/number}",
            "milestones_url": "https://api.github.com/repos/Kraken-CI/kraken/milestones{/number}",
            "notifications_url": "https://api.github.com/repos/Kraken-CI/kraken/notifications{?since,all,participating}",
            "labels_url": "https://api.github.com/repos/Kraken-CI/kraken/labels{/name}",
            "releases_url": "https://api.github.com/repos/Kraken-CI/kraken/releases{/id}",
            "deployments_url": "https://api.github.com/repos/Kraken-CI/kraken/deployments",
            "created_at": "2020-07-19T09:22:37Z",
            "updated_at": "2020-12-09T18:54:32Z",
            "pushed_at": "2020-12-09T19:47:00Z",
            "git_url": "git://github.com/Kraken-CI/kraken.git",
            "ssh_url": "git@github.com:Kraken-CI/kraken.git",
            "clone_url": "https://github.com/Kraken-CI/kraken.git",
            "svn_url": "https://github.com/Kraken-CI/kraken",
            "homepage": "https://kraken.ci/",
            "size": 1134,
            "stargazers_count": 3,
            "watchers_count": 3,
            "language": "Python",
            "has_issues": True,
            "has_projects": True,
            "has_downloads": True,
            "has_wiki": True,
            "has_pages": False,
            "forks_count": 0,
            "mirror_url": None,
            "archived": False,
            "disabled": False,
            "open_issues_count": 30,
            "license": {
              "key": "apache-2.0",
              "name": "Apache License 2.0",
              "spdx_id": "Apache-2.0",
              "url": "https://api.github.com/licenses/apache-2.0",
              "node_id": "MDc6TGljZW5zZTI="
            },
            "forks": 0,
            "open_issues": 30,
            "watchers": 3,
            "default_branch": "master"
          },
          "organization": {
            "login": "Kraken-CI",
            "id": 68497961,
            "node_id": "MDEyOk9yZ2FuaXphdGlvbjY4NDk3OTYx",
            "url": "https://api.github.com/orgs/Kraken-CI",
            "repos_url": "https://api.github.com/orgs/Kraken-CI/repos",
            "events_url": "https://api.github.com/orgs/Kraken-CI/events",
            "hooks_url": "https://api.github.com/orgs/Kraken-CI/hooks",
            "issues_url": "https://api.github.com/orgs/Kraken-CI/issues",
            "members_url": "https://api.github.com/orgs/Kraken-CI/members{/member}",
            "public_members_url": "https://api.github.com/orgs/Kraken-CI/public_members{/member}",
            "avatar_url": "https://avatars3.githubusercontent.com/u/68497961?v=4",
            "description": None
          },
          "sender": {
            "login": "godfryd",
            "id": 176567,
            "node_id": "MDQ6VXNlcjE3NjU2Nw==",
            "avatar_url": "https://avatars1.githubusercontent.com/u/176567?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/godfryd",
            "html_url": "https://github.com/godfryd",
            "followers_url": "https://api.github.com/users/godfryd/followers",
            "following_url": "https://api.github.com/users/godfryd/following{/other_user}",
            "gists_url": "https://api.github.com/users/godfryd/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/godfryd/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/godfryd/subscriptions",
            "organizations_url": "https://api.github.com/users/godfryd/orgs",
            "repos_url": "https://api.github.com/users/godfryd/repos",
            "events_url": "https://api.github.com/users/godfryd/events{/privacy}",
            "received_events_url": "https://api.github.com/users/godfryd/received_events",
            "type": "User",
            "site_admin": False
          }
        }

    data = json.dumps(payload)

    req = urllib.request.Request("http://localhost:8080/webhooks/2/github", data.encode('utf-8'))

    # Request URL: http://lab.kraken.ci:
    # Request method: POST
    # Accept: */*
    # content-type: application/json
    # User-Agent: GitHub-Hookshot/a9cf1f2
    # X-GitHub-Delivery: 4e010eb0-3a57-11eb-83b5-8eaf736bdba8
    req.add_header('X-GitHub-Event', 'pull_request')
    # X-GitHub-Hook-ID: 243263944
    # X-GitHub-Hook-Installation-Target-ID: 280832057
    # X-GitHub-Hook-Installation-Target-Type: repository
    req.add_header('X-Hub-Signature', 'sha1=c7bb693914eba83116d10e1c158660ce577ba729')
    # X-Hub-Signature-256: sha256=d688709b3cc5766144d0949baf0e5c13338bfb7216b02d1d89ffc3c246e4e073

    with urllib.request.urlopen(req) as f:
        print(f.read())


def main():
    #do_pull_request()
    do_push()

if __name__ == '__main__':
    main()
