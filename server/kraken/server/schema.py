# Copyright 2020 The Kraken Authors
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

import RestrictedPython
from RestrictedPython import compile_restricted
from RestrictedPython import limited_builtins


class SchemaCodeContext:
    def __init__(self, branch_name):
        self.branch_name = branch_name


def execute_schema_code(branch, schema_code):
    # TODO: use starlark-go for executing schema code
    # for now RestrictedPython is used
    byte_code = compile_restricted(schema_code, '<inline>', 'exec')

    my_locals = {}
    my_globals = {'__builtins__': limited_builtins,
                  '_getiter_': RestrictedPython.Eval.default_guarded_getiter,
                  '_iter_unpack_sequence_': RestrictedPython.Guards.guarded_iter_unpack_sequence}

    exec(byte_code, my_globals, my_locals)  # pylint: disable=exec-used

    my_globals.update(my_locals)
    ctx = SchemaCodeContext(branch.name)
    my_globals['ctx'] = ctx

    my_locals2 = {}
    exec('schema = stage(ctx)', my_globals, my_locals2)
    schema = my_locals2['schema']

    return schema
