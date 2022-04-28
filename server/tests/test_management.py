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


import pytest

import werkzeug.exceptions

from kraken.server import initdb
from kraken.server.models import db, Project, Branch

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
