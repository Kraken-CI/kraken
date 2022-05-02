# Copyright 2022 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

import pytest
from hamcrest import assert_that, has_entries, matches_regexp, contains_exactly, instance_of

import werkzeug.exceptions

from kraken.server import consts, initdb, utils
from kraken.server.models import db, Project, Branch, Flow

from common import create_app

from kraken.server import management


@pytest.mark.db
def test_move_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj1 = Project(name='proj-1')
        proj2 = Project(name='proj-2')
        br = Branch(name='br', project=proj1)
        db.session.commit()

        with pytest.raises(werkzeug.exceptions.NotFound):
            management.move_branch(123, {})

        with pytest.raises(werkzeug.exceptions.BadRequest):
            management.move_branch(br.id, {})

        assert br.project_id == proj1.id

        # move branch to new project
        management.move_branch(br.id, {'project_id': proj2.id})
        assert br.project_id == proj2.id

        # move branch brack to previous project
        management.move_branch(br.id, {'project_id': proj1.id})
        assert br.project_id == proj1.id


@pytest.mark.db
def test_get_branch_stats():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1')
        br = Branch(name='br', project=proj)
        fc1 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=1)
        fc2 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=2)
        fc3 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=3)
        fc4 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=4)
        fc5 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=1)
        fd1 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd2 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd3 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd4 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        db.session.commit()

        today = utils.utcnow()
        two_weeks_ago = today - datetime.timedelta(days=14)
        two_months_ago = today - datetime.timedelta(days=60)
        fc1.created = two_months_ago
        fc1.finished = fc1.created + datetime.timedelta(seconds=60)
        fc2.created = two_months_ago + datetime.timedelta(seconds=10)
        fc3.created = two_weeks_ago
        fc3.finished = fc3.created + datetime.timedelta(seconds=180)
        fc4.created = two_weeks_ago + datetime.timedelta(seconds=10)
        fc4.finished = fc4.created + datetime.timedelta(seconds=120)
        fd1.created = two_months_ago
        fd1.finished = fd1.created + datetime.timedelta(seconds=30)
        fd2.created = two_months_ago + datetime.timedelta(seconds=10)
        fd2.finished = fd2.created + datetime.timedelta(seconds=60)
        fd3.created = two_weeks_ago
        fd3.finished = fd3.created + datetime.timedelta(seconds=30)
        fd4.finished = fd4.created + datetime.timedelta(seconds=90)
        db.session.commit()

        with pytest.raises(werkzeug.exceptions.NotFound):
            management.get_branch_stats(123)

        resp, code = management.get_branch_stats(br.id)
        assert code == 200
        # assert resp is None
        lbl_re = matches_regexp(r'\d+\.')
        assert_that(resp, has_entries({
            'id': br.id,
            'ci': has_entries({
                'flows_total': 5,
                'flows_last_month': 3,
                'flows_last_week': 1,
                'avg_duration_last_month': '2m 30s',
                'avg_duration_last_week': None,
                'durations': instance_of(list),
            }),
            'dev': has_entries({
                'flows_total': 4,
                'flows_last_month': 2,
                'flows_last_week': 1,
                'avg_duration_last_month': '0s',
                'avg_duration_last_week': '1m 30s',
                'durations': instance_of(list),
            }),
        }))

        assert_that(resp['ci']['durations'],
                    contains_exactly(has_entries({'flow_label': lbl_re, 'duration': 60}),
                                     has_entries({'flow_label': lbl_re, 'duration': None}),
                                     has_entries({'flow_label': lbl_re, 'duration': 180}),
                                     has_entries({'flow_label': lbl_re, 'duration': 120}),
                                     has_entries({'flow_label': lbl_re, 'duration': None})))

        assert_that(resp['dev']['durations'],
                    contains_exactly(has_entries({'flow_label': lbl_re, 'duration': 30}),
                                     has_entries({'flow_label': lbl_re, 'duration': 60}),
                                     has_entries({'flow_label': lbl_re, 'duration': 30}),
                                     has_entries({'flow_label': lbl_re, 'duration': 90})))


def test_get_workflow_schema():
    app = create_app()

    with app.app_context():
        schema, code = management.get_workflow_schema()
        assert schema
        assert code == 200
