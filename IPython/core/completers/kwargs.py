# encoding: utf-8
"""
"""
#-----------------------------------------------------------------------------
#  Copyright (C) 2013 The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import re
import inspect

from IPython.core.completer2 import BaseCompleter

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class KeywordArgCompleter(BaseCompleter):
    """Match named parameters (kwargs) of the last open function"""

    # regexp to parse docstring for function signature
    docstring_sig_re = re.compile(r'^[\w|\s.]+\(([^)]*)\).*')
    docstring_kwd_re = re.compile(r'[\s|\[]*(\w+)(?:\s*=\s*.*)')

    def match(self, event):
        if "." in event.text or '(' not in event.line:
            # a keyword cannot have a dot in it
            # the line must have a paren -- we don't want to trigger
            # tokenization if we don't need to
            return None

        # 1. find the nearest identifier that comes before an unclosed
        # parenthesis before the cursor
        # e.g. for "foo (1+bar(x), pa<cursor>,a=1)", the candidate is "foo"
        try:
            ids = last_open_identifier(event.tokens)[0]
        except ValueError:
            return None

        if len(ids) == 1:
            name = ids[0]
        else:
            name = '.'.ids[::-1].join()

        try:
            obj = eval(name, self.shell.user_ns)
        except:
            try:
                obj = eval(name, self.shell.user_global_ns)
            except:
                return None

        named_args = self.default_arguments(obj)
        matches = set()
        for named_arg in named_args:
            if named_arg.startswith(event.text):
                matches.add('%s=' % named_arg)
        return {'kwargs': matches}

    def default_arguments(self, obj):
        """Find the default arguments of a callable

        This method trys both using the inspect module, and by limited
        parsing of the docstring.

        Parameters
        ----------
        obj : callable
            obj should be a function, method, class, etc.

        Returns
        -------
        arguments : set
            A set of strings, containing the names of the arguments that
            accept a default value
        """
        call_obj = obj
        arguments = set()

        if inspect.isbuiltin(obj):
            return arguments

        if not (inspect.isfunction(obj) or inspect.ismethod(obj)):
            if inspect.isclass(obj):
                # for cython embededsignature=True the constructor docstring
                # belongs to the object itself not __init__
                arguments.add(self.default_arguments_from_docstring(
                            getattr(obj, '__doc__', '')))
                # for classes, check for __init__, __new__
                call_obj = (getattr(obj, '__init__', None) or
                       getattr(obj, '__new__', None))
            # for all others, check if they are __call__able
            elif hasattr(obj, '__call__'):
                call_obj = obj.__call__

        arguments.update(self.default_arguments_from_docstring(
                getattr(call_obj, '__doc__', '')))

        try:
            args, _, _1, defaults = inspect.getargspec(call_obj)
            if defaults:
                arguments.update(args[-len(defaults):])
        except TypeError:
            pass

        return arguments

    def default_arguments_from_docstring(self, docstring):
        """Parse the first line of docstring for call signature.

        Docstring should be of the form 'min(iterable[, key=func])\n'.
        It can also parse cython docstring of the form
        'Minuit.migrad(self, int ncall=10000, resume=True, int nsplit=1)'.
        """
        arguments = set()

        if docstring is None:
            return arguments

        #care only the firstline
        line = docstring.lstrip().splitlines()[0]

        #p = re.compile(r'^[\w|\s.]+\(([^)]*)\).*')
        #'min(iterable[, key=func])\n' -> 'iterable[, key=func]'
        signature = self.docstring_sig_re.search(line)
        if not signature:
            return arguments

        # iterable[, key=func]' -> ['iterable[' ,' key=func]']
        for s in signature.group(0).split(','):
            arguments.add(self.docstring_kwd_re.findall(s))

        return arguments


def last_open_identifier(tokens):
    """Find the the nearest identifier (function/method/callable name)
    that comes before the last unclosed parentheses

    Parameters
    ----------
    tokens : list of strings
        tokens should be a list of python tokens produced by splitting
        a line of input

    Returns
    -------
    identifiers : list
        A list of tokens from `tokens` that are identifiers for the function
        or method that comes before an unclosed partentheses
    call_tokens : list
        The subset of the tokens that occur after `identifiers` in the input,
        starting with the open parentheses of the function call

    Raises
    ------
    ValueError if the line doesn't match

    See Also
    --------
    tokenize : to generate `tokens`
    cursor_argument
    """

    # 1. pop off the tokens until we get to the first unclosed parens
    # as we pop them off, store them in a list
    iterTokens = iter(reversed(tokens))
    tokens_after_identifier = []

    openPar = 0  # number of open parentheses
    for token in iterTokens:
        tokens_after_identifier.insert(0, token)
        if token == ')':
            openPar -= 1
        elif token == '(':
            openPar += 1
            if openPar > 0:
                # found the last unclosed parenthesis
                break
    else:
        raise ValueError()

    # 2. Concatenate dotted names ("foo.bar" for "foo.bar(x, pa" )
    identifiers = []
    isId = re.compile(r'\w+$').match
    while True:
        try:
            identifiers.append(next(iterTokens))
            if not isId(identifiers[-1]):
                identifiers.pop()
                break
            if not next(iterTokens) == '.':
                break
        except StopIteration:
            break

    return identifiers[::-1], tokens_after_identifier
