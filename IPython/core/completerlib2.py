# encoding: utf-8
"""Completion matchers for IPython
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

import os
import glob
import sys
import re
import inspect
import __builtin__
import keyword
from collections import defaultdict


from IPython.core.inputsplitter import ESC_MAGIC
from IPython.utils import generics
from IPython.utils.process import arg_split
from IPython.core.completer2 import BaseMatcher
from IPython.utils.dir2 import dir2
from IPython.utils.traitlets import CBool, Enum
#from IPython.core.interactiveshell import InteractiveShell

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

# Public API
__all__ = ['GlobalMatcher', 'AttributeMatcher', 'FileMatcher',
           'MagicsMatcher', 'AliasMatcher', 'KeywordArgMatcher']

if sys.platform == 'win32':
    PROTECTABLES = ' '
else:
    PROTECTABLES = ' ()[]{}?=\\|;:\'#*"^&'

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class GlobalMatcher(BaseMatcher):
    """Match python keywords, builtins, and variables
    in the local scope.
    """

    def match(self, event):
        if "." in event.text:
            return None
        matches = defaultdict(lambda: set())
        n = len(event.text)
        for kind, lst in (('keywords', keyword.kwlist),
                          ('locals', self.shell.user_ns.keys()),
                          ('locals', self.shell.user_global_ns.keys()),
                          ('builtins', __builtin__.__dict__)):
            for word in lst:
                if word[:n] == event.text and word != '__builtins__':
                    matches[kind].add(word)

        return matches


class AttributeMatcher(BaseMatcher):
    """Compute matches when text contains a dot.

    Assuming the text is of the form NAME.NAME....[NAME], and is
    evaluatable in the namespace it will be evaluated and its attributes
    (as revealed by dir()) are used as possible completions.
    (For class instances, class members are are also considered.)

    WARNING: this can still invoke arbitrary C code, if an object
    with a __getattr__ hook is evaluated.
    """

    limit_to__all__ = CBool(default_value=False, config=True,
        help="""Instruct the completer to use __all__ for the completion

        Specifically, when completing on ``object.<tab>``.

        When True: only those names in obj.__all__ will be included.

        When False [default]: the __all__ attribute is ignored""")

    omit__names = Enum((0, 1, 2), default_value=2, config=True,
        help="""Instruct the completer to omit private method names

        Specifically, when completing on ``object.<tab>``.

        When 2 [default]: all names that start with '_' will be excluded.

        When 1: all 'magic' names (``__foo__``) will be excluded.

        When 0: nothing will be excluded.""")

    attr_re = re.compile(r"(\S+(\.\w+)*)\.(\w*)$")
    greedy_attr_re = re.compile(r"(.+)\.(\w*)$")

    def match(self, event):
        m1 = self.attr_re.match(event.text)
        if m1:
            expr, attr = m1.group(1, 3)
        elif event.manager.greedy:
            # if the user wants greedy semantics, then we match
            # such that attr might actually contain function calls
            m2 = self.greedy_attr_re.match(event.line)
            if m2:
                expr, attr = m2.group(1, 2)
            else:
                return None
        else:
            return None

        try:
            # find the object in the namespace that the user is
            # refering to
            obj = eval(expr, self.shell.user_ns)
        except:
            try:
                obj = eval(expr, self.shell.user_global_ns)
            except:
                # raise
                return None

        # get all of the attributes of that object
        if self.limit_to__all__ and hasattr(obj, '__all__'):
            # either by looking in __all__
            try:
                words = [w for w in getattr(obj, '__all__') if isinstance(w, basestring)]
            except:
                return None
        else:
            # or by running dir()
            words = dir2(obj)

        # run a special (documented?) "generic hook" that allows users
        # to define custom matches on object attributes
        try:
            words = generics.complete_object(obj, words)
        except:
            pass

        if event.text.endswith('.') and self.omit__names:
            if self.omit__names == 1:
                # filter out matches like __stuff__
                words = [w for w in words if not w.startswith('__') and w.endswith('__')]
            else:
                # filter out any match that starts with '_'
                words = [w for w in words if not w.startswith('_')]

        n = len(attr)
        res = ["%s.%s" % (expr, w) for w in words if w[:n] == attr]
        return {'attributes': set(res)}


class FileMatcher(BaseMatcher):
    """Match filenames, expanding ~USER type strings.

    Most of the seemingly convoluted logic in this completer is an
    attempt to handle filenames with spaces in them.  And yet it's not
    quite perfect, because Python's readline doesn't expose all of the
    GNU readline details needed for this to be done correctly.

    For a filename with a space in it, the printed completions will be
    only the parts after what's already been typed (instead of the
    full completions, as is normally done).  I don't think with the
    current (as of Python 2.3) Python readline it's possible to do
    better."""

    def _clean_glob(self, text):
        return self.glob("%s*" % text)

    def _clean_glob_win32(self, text):
        return [f.replace("\\", "/")
                for f in self.glob("%s*" % text)]

    def __init__(self, shell, config=None):
        super(FileMatcher, self).__init__(shell, config=config)

        # Hold a local ref. to glob.glob for speed
        self.glob = glob.glob

        if sys.platform == "win32":
            self.clean_glob = self._clean_glob_win32
        else:
            self.clean_glob = self._clean_glob

    def match(self, event):
        # chars that require escaping with backslash - i.e. chars
        # that readline treats incorrectly as delimiters, but we
        # don't want to treat as delimiters in filename matching
        # when escaped with backslash

        line, text = event.line, event.text
        if text.startswith('!'):
            text = text[1:]
            text_prefix = '!'
        else:
            text_prefix = ''

        # track strings with open quotes
        open_quotes = has_open_quotes(line)

        if '(' in line or '[' in line:
            lsplit = text
        else:
            try:
                # arg_split ~ shlex.split, but with unicode bugs fixed by us
                lsplit = arg_split(line)[-1]
            except ValueError:
                # typically an unmatched ", or backslash without escaped char.
                if open_quotes:
                    lsplit = line.split(open_quotes)[-1]
                else:
                    return None
            except IndexError:
                # tab pressed on empty line
                lsplit = ""

        if not open_quotes and lsplit != protect_filename(lsplit):
            # if protectables are found, do matching on the whole escaped name
            has_protectables = True
            text0, text = text, lsplit
        else:
            has_protectables = False
            text = os.path.expanduser(text)

        matches = {'directories': set(), 'files': set()}

        if text == "":
            for f in self.glob("*"):
                match = text_prefix + protect_filename(f)
                if os.path.isdir(f):
                    matches['directories'].add(match + '/')
                else:
                    matches['files'].add(match)
            return matches

        # Compute the matches from the filesystem
        m0 = self.clean_glob(text.replace('\\', ''))

        if has_protectables:
            # If we had protectables, we need to revert our changes to the
            # beginning of filename so that we don't double-write the part
            # of the filename we have so far
            len_lsplit = len(lsplit)
            for f in m0:
                match = text_prefix + text0 + protect_filename(f[len_lsplit:])
                if os.path.isdir(f):
                    matches['directories'].add(f + '/')
                else:
                    matches['files'].add(f)

        else:
            if open_quotes:
                # if we have a string with an open quote, we don't need to
                # protect the names at all (and we _shouldn't_, as it
                # would cause bugs when the filesystem call is made).
                matches = m0
            else:
                for f in m0:
                    if os.path.isdir(f):
                        matches['directories'].add(f + '/')
                    else:
                        matches['files'].add(f)

        if len(matches['files']) == 0 and len(matches['directories']) == 0:
            return None

        # Mark directories in input list by appending '/' to their names.
        return matches


class MagicsMatcher(BaseMatcher):
    """Match magics"""

    def match(self, event):

        #print 'Completer->magic_matches:',text,'lb',self.text_until_cursor # dbg
        # Get all shell magics now rather than statically, so magics loaded at
        # runtime show up too.
        lsm = self.shell.magics_manager.lsmagic()
        line_magics = lsm['line']
        cell_magics = lsm['cell']

        pre = ESC_MAGIC
        pre2 = pre+pre

        # Completion logic:
        # - user gives %%: only do cell magics
        # - user gives %: do both line and cell magics
        # - no prefix: do both
        # In other words, line magics are skipped if the user gives %% explicitly
        bare_text = event.text.lstrip(pre)
        matches = [pre2 + m for m in cell_magics if m.startswith(bare_text)]
        if not event.text.startswith(pre2):
            matches += [pre + m for m in line_magics if m.startswith(bare_text)]

        return {'magics': set(matches)}


class AliasMatcher(BaseMatcher):
    """Match internal system aliases"""

    def match(self, event):
        line, text = event.line, event.text

        # if we are not in the first 'item', alias matching
        # doesn't make sense - unless we are starting with 'sudo' command.
        if ' ' in line and not line.startswith('sudo'):
            return None

        text = os.path.expanduser(text)
        aliases = self.shell.alias_manager.alias_table.keys()
        if text == '':
            matches = aliases
        else:
            matches = [a for a in aliases if a.startswith(text)]
        return {'aliases': matches}


class KeywordArgMatcher(BaseMatcher):
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


#-----------------------------------------------------------------------------
# "Exclusive" completers
# these only respond in certain cases, but when they do they give the
# only results shown to the user
#-----------------------------------------------------------------------------

class CDMatcher(FileMatcher):
    """Matcher that returns only directories for `cd`
    """

    # this is an `exclusive` matcher, which means only its results
    # will be shown to the user, if it returns any. results from all
    # other matchers will be excluded
    exclusive = CBool(True)

    def match(self, event):
        # check that the user entered cd as the first item
        # on the line
        if event.split[0] == 'cd' and len(event.split) > 1:
            filesystem_matches = super(CDMatcher, self).match(event)
            if filesystem_matches:
                return {'directories': filesystem_matches['directories']}

        # Note, we need to add more features here, including
        # the bookmarks and _dh stuff, to replicate what is currently
        # available in the old cd completer
        return None


class AliasLineMatcher(FileMatcher):
    """This matcher does bash style completion when the line starts with
    an alias, since aliases call directly to bash
    """
    exclusive = CBool(True)

    def match(self, event):
        have_matches = False
        if event.split[0] not in self.shell.alias_manager.alias_table.keys():
            return None

        matches = super(AliasLineMatcher, self).match(event)
        if matches is not None:
            have_matches = True
            matches['locals'] = set()
        else:
            matches = {'locals': set()}

        text = event.text

        if (text == '' and event.tokens[-1] == '{') or event.tokens[-2] == '{':
            prefix = ''
        else:
            prefix = '{'


        n = len(text)
        for word in set.union(set(self.shell.user_ns.keys()),
                              set(self.shell.user_global_ns.keys())):
            if word[:n] == text and not word.startswith('_'):
                try:
                    obj = eval(word, self.shell.user_ns)
                except:
                    continue

                if isinstance(obj, int) or isinstance(obj, basestring):
                    have_matches = True
                    matches['locals'].add(prefix + word + '}')

        if have_matches:
            return matches
        return None




#-----------------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------------


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


def has_open_quotes(s):
    """Return whether a string has open quotes.

    This simply counts whether the number of quote characters of either type in
    the string is odd.

    Returns
    -------
    If there is an open quote, the quote character is returned.  Else, return
    False.
    """
    # We check " first, then ', so complex cases with nested quotes will get
    # the " to take precedence.
    if s.count('"') % 2:
        return '"'
    elif s.count("'") % 2:
        return "'"
    else:
        return False


def protect_filename(s):
    """Escape a string to protect certain characters."""

    return "".join([(ch in PROTECTABLES and '\\' + ch or ch)
                    for ch in s])
