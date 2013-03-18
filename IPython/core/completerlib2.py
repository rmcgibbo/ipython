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
import __builtin__
import keyword
from collections import defaultdict

from IPython.utils import generics
from IPython.utils.process import arg_split
from IPython.core.completer2 import BaseMatcher
from IPython.utils.dir2 import dir2
from IPython.utils.traitlets import CBool, Enum

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

# Public API
__all__ = ['GlobalMatcher', 'AttributeMatcher', 'FileMatcher']

if sys.platform == 'win32':
    PROTECTABLES = ' '
else:
    PROTECTABLES = ' ()[]{}?=\\|;:\'#*"^&'

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class GlobalMatcher(BaseMatcher):
    """Match python keywords, bultins, and variables
    in the local scope.

    TODO: Figure out how to customize the namespace. It's
    going to need to be passed in, not grabbed with get_ipython()
    """

    def match(self, event):
        if "." in event.text:
            return None

        matches = defaultdict(lambda: set())
        n = len(event.text)
        for kind, lst in (('keywords', keyword.kwlist),
                          ('locals', event.manager.namespace.keys()),
                          ('bultins', __builtin__.__dict__)):
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
            obj = eval(expr, event.manager.namespace)
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

    def __init__(self, config=None):
        super(FileMatcher, self).__init__(config=config)

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
                    return []
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

        if text == "":
            return [text_prefix + protect_filename(f) for f in self.glob("*")]

        # Compute the matches from the filesystem
        m0 = self.clean_glob(text.replace('\\', ''))

        if has_protectables:
            # If we had protectables, we need to revert our changes to the
            # beginning of filename so that we don't double-write the part
            # of the filename we have so far
            len_lsplit = len(lsplit)
            matches = [text_prefix + text0 +
                       protect_filename(f[len_lsplit:]) for f in m0]
        else:
            if open_quotes:
                # if we have a string with an open quote, we don't need to
                # protect the names at all (and we _shouldn't_, as it
                # would cause bugs when the filesystem call is made).
                matches = m0
            else:
                matches = [text_prefix + protect_filename(f) for f in m0]

        if len(matches) == 0:
            return None

        # Mark directories in input list by appending '/' to their names.
        matches = [x + '/' if os.path.isdir(x) else x for x in matches]
        return {'files': set(matches)}


#-----------------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------------


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
