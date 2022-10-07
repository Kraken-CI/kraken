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

from contextlib import contextmanager

## vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
## copied from https://github.com/pycasbin/sqlalchemy-adapter/blob/606a631b1704d76c5ca0f83064158604851dc17f/casbin_sqlalchemy_adapter/adapter.py
## this is under apache 2.0 license


import casbin
from casbin import persist
from sqlalchemy import or_
from werkzeug.exceptions import Forbidden

from .models import db, CasbinRule


class Filter:
    ptype = []
    v0 = []
    v1 = []
    v2 = []
    v3 = []
    v4 = []
    v5 = []


class Adapter(persist.Adapter, persist.adapters.UpdateAdapter):
    """the interface for Casbin adapters."""

    def __init__(self, filtered=False):
        self._filtered = filtered

    @contextmanager
    def _session_scope(self):
        """Provide a transactional scope around a series of operations."""
        try:
            yield
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    def load_policy(self, model):
        """loads all policy rules from the storage."""
        with self._session_scope():
            lines = CasbinRule.query.all()
            for line in lines:
                persist.load_policy_line(str(line), model)

    def is_filtered(self):
        return self._filtered

    def load_filtered_policy(self, model, flter) -> None:
        """loads all policy rules from the storage."""
        with self._session_scope():
            q = CasbinRule.query
            q = self.filter_query(q, flter)
            filtered = q.all()

            for line in filtered:
                persist.load_policy_line(str(line), model)
            self._filtered = True

    def filter_query(self, querydb, flter):
        for attr in ("ptype", "v0", "v1", "v2", "v3", "v4", "v5"):
            if len(getattr(flter, attr)) > 0:
                querydb = querydb.filter(
                    getattr(CasbinRule, attr).in_(getattr(flter, attr))
                )
        return querydb.order_by(CasbinRule.id)

    def _save_policy_line(self, ptype, rule):
        with self._session_scope():
            line = CasbinRule(ptype=ptype)
            for i, v in enumerate(rule):
                setattr(line, "v{}".format(i), v)
            # session.add(line)

    def save_policy(self, model):
        """saves all policy rules to the storage."""
        with self._session_scope():
            CasbinRule.query.delete()
            for sec in ["p", "g"]:
                if sec not in model.model.keys():
                    continue
                for ptype, ast in model.model[sec].items():
                    for rule in ast.policy:
                        self._save_policy_line(ptype, rule)
        return True

    def add_policy(self, sec, ptype, rule):  # pylint: disable=unused-argument
        """adds a policy rule to the storage."""
        self._save_policy_line(ptype, rule)

    def add_policies(self, sec, ptype, rules):  # pylint: disable=unused-argument
        """adds a policy rules to the storage."""
        for rule in rules:
            self._save_policy_line(ptype, rule)

    def remove_policy(self, sec, ptype, rule):  # pylint: disable=unused-argument
        """removes a policy rule from the storage."""
        with self._session_scope():
            q = CasbinRule.query.filter_by(ptype=ptype)
            for i, v in enumerate(rule):
                q = q.filter(getattr(CasbinRule, "v{}".format(i)) == v)
            r = q.delete()

        return r > 0

    def remove_policies(self, sec, ptype, rules):  # pylint: disable=unused-argument
        """remove policy rules from the storage."""
        if not rules:
            return
        with self._session_scope():
            q = CasbinRule.query.filter_by(ptype=ptype)
            rules = zip(*rules)
            for i, rule in enumerate(rules):
                q = q.filter(
                    or_(getattr(CasbinRule, "v{}".format(i)) == v for v in rule)
                )
            q.delete()

    def remove_filtered_policy(self, sec, ptype, field_index, *field_values):  # pylint: disable=unused-argument
        """removes policy rules that match the filter from the storage.
        This is part of the Auto-Save feature.
        """
        with self._session_scope():
            q = CasbinRule.query.filter_by(ptype=ptype)

            if not (0 <= field_index <= 5):
                return False
            if not (1 <= field_index + len(field_values) <= 6):
                return False
            for i, v in enumerate(field_values):
                if v != "":
                    v_value = getattr(CasbinRule, "v{}".format(field_index + i))
                    q = q.filter(v_value == v)
            r = q.delete()

        return r > 0

    def update_policy(
        self, sec: str, ptype: str, old_rule: [str], new_rule: [str]
    ) -> None:  # pylint: disable=unused-argument
        """
        Update the old_rule with the new_rule in the database (storage).

        :param sec: section type
        :param ptype: policy type
        :param old_rule: the old rule that needs to be modified
        :param new_rule: the new rule to replace the old rule

        :return: None
        """

        with self._session_scope():
            q = CasbinRule.query.filter_by(ptype=ptype)

            # locate the old rule
            for index, value in enumerate(old_rule):
                v_value = getattr(CasbinRule, "v{}".format(index))
                q = q.filter(v_value == value)

            # need the length of the longest_rule to perform overwrite
            longest_rule = old_rule if len(old_rule) > len(new_rule) else new_rule
            old_rule_line = q.one()

            # overwrite the old rule with the new rule
            for index in range(len(longest_rule)):
                if index < len(new_rule):
                    exec(f"old_rule_line.v{index} = new_rule[{index}]")
                else:
                    exec(f"old_rule_line.v{index} = None")

    def update_policies(
        self,
        sec: str,
        ptype: str,
        old_rules: [
            [str],
        ],
        new_rules: [
            [str],
        ],
    ) -> None:
        """
        Update the old_rules with the new_rules in the database (storage).

        :param sec: section type
        :param ptype: policy type
        :param old_rules: the old rules that need to be modified
        :param new_rules: the new rules to replace the old rules

        :return: None
        """
        for i in range(len(old_rules)):
            self.update_policy(sec, ptype, old_rules[i], new_rules[i])

    def update_filtered_policies(
        self, sec, ptype, new_rules: [[str]], field_index, *field_values
    ) -> [[str]]:
        """update_filtered_policies updates all the policies on the basis of the filter."""

        flter = Filter()
        flter.ptype = ptype

        # Creating Filter from the field_index & field_values provided
        for i in range(len(field_values)):
            if field_index <= i and i < field_index + len(field_values):
                setattr(flter, f"v{i}", field_values[i - field_index])
            else:
                break

        self._update_filtered_policies(new_rules, flter)

    def _update_filtered_policies(self, new_rules, flter) -> [[str]]:
        """_update_filtered_policies updates all the policies on the basis of the filter."""

        with self._session_scope():

            # Load old policies
            q = CasbinRule.query.filter_by(ptype=flter.ptype)
            q = self.filter_query(q, flter)
            old_rules = q.all()

            # Delete old policies
            self.remove_policies("p", flter.ptype, old_rules)

            # Insert new policies
            self.add_policies("p", flter.ptype, new_rules)

            # return deleted rules
            return old_rules


## ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



enforcer = None

def init():
    global enforcer
    if enforcer:
        return

    adapter = Adapter()

    # Create a config model policy
    model_txt = """
        [request_definition]
        r = sub, obj, act

        [policy_definition]
        p = sub, obj, act

        [role_definition]
        g = _, _
        g2 = _, _

        [policy_effect]
        e = some(where (p.eft == allow))

        [matchers]
        m = (g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act) || g2(r.sub, 'superadmin') || r.sub == '1'
    """
    model = casbin.Enforcer.new_model(text=model_txt)

    # Create enforcer from adapter and config policy
    enforcer = casbin.Enforcer(model, adapter)


def check(token_info, obj, act, msg):
    if not enforcer.enforce(str(token_info['sub'].id), str(obj), str(act)):
        raise Forbidden(msg)
