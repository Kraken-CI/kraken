# Copyright 2021 The Kraken Authors
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


from flask import abort, Response, redirect

from .models import Branch


def get_branch_badge(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    label = 'Kraken Build of %s' % branch.name
    label = label.replace('-', '_')

    flow = branch.ci_last_completed_flow

    if not flow:
        url = 'https://img.shields.io/badge/%s-%s-%s' % (label, 'no flows yet', 'informational')
        return redirect(url)


    if not flow.runs:
        url = 'https://img.shields.io/badge/%s-%s-%s' % (label, 'no runs', 'informational')
        return redirect(url)

    errors = any((r.jobs_error > 0 for r in flow.runs))

    msg = '%s ' % flow.get_label()
    if errors:
        color = 'critical'
        msg += 'failed'
    else:
        color = 'success'
        msg += 'success'

    url = 'https://img.shields.io/badge/%s-%s-%s' % (label, msg, color)
    return redirect(url)
