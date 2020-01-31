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

    ctx = SchemaCodeContext(branch.name)
    schema = my_locals['stage'](ctx)
    return schema
