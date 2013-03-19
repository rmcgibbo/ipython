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

import glob
import sys
import os

from IPython.utils.traitlets import CBool
from IPython.utils.process import arg_split
from IPython.core.completer2 import BaseCompleter

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

if sys.platform == 'win32':
    PROTECTABLES = ' '
else:
    PROTECTABLES = ' ()[]{}?=\\|;:\'#*"^&'

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class FileCompleter(BaseCompleter):
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
        super(FileCompleter, self).__init__(shell, config=config)

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


class CDCompleter(FileCompleter):
    """Completer that returns only directories for `cd`
    """

    # this is an `exclusive` Completer, which means only its results
    # will be shown to the user, if it returns any. results from all
    # other Completers will be excluded
    exclusive = CBool(True)

    def match(self, event):
        # check that the user entered cd as the first item
        # on the line
        if event.split[0] == 'cd' and len(event.split) > 1:
            filesystem_matches = super(CDCompleter, self).match(event)
            if filesystem_matches:
                return {'directories': filesystem_matches['directories']}

        # Note, we need to add more features here, including
        # the bookmarks and _dh stuff, to replicate what is currently
        # available in the old cd completer
        return None


class ShellLineCompleter(FileCompleter):
    """
    If the line starts with either an alias or with the '!' character,
    the string is invoked (almost) directly in sh, so we want to do
    simple bash-style completion.

    The one ipython specific thing here is that the user can quote
    python variables inside of mustsashes. So let's recommend some of
    those too, in addition to files and direcrories.

    There's a slight trickiness, which is that since the mustasche is an
    RL delimiter, we can't do perfectly...
    """
    exclusive = CBool(True)

    def match(self, event):
        have_matches = False
        aliases = self.shell.alias_manager.alias_table.keys()
        
        # only respond when the first item on the line is the name of an
        # alias, or the line starts with a bang.
        if not ((event.split[0] in aliases) or (len(event.line) > 0 and \
                                                event.line[0] == '!')):
            return None

        matches = super(ShellLineCompleter, self).match(event)
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
