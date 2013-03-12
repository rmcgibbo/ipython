# encoding: utf-8
"""Word completion for IPython.
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
import abc

# from IPython.utils.traitlets import CBool, Enum


DELIMS = ' \t\n`!@#$^&*()=+[{]}\\|;:\'",<>?'
GREEDY_DELIMS = ' =\r\n'

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class CompletionManager(Configurable):
    def __init__(self, config=None):
        self.splitter = CompletionSplitter()
    
    def register_completer(self, completer):
        """Register a new completer
        """
        pass

    def complete(self, block, cursor_position=None):
        """Recommend possible completions for a given input block

        Parameters
        ----------
        block : str
            Either a line of text or an entire block of text (e.g. a cell)
            providing the current completion context.
        cursor_position : int, optional
            The position of the cursor within the line, at the time that
            the completion key was activated. If not supplied, the cursor
            will be assumed to have been at the end of the line.

        Returns
        -------
        completions : dict, {str -> list(str)}
            The keys of the completions dict are the 'kind' of the completion,
            which may be displayed in rich frontends. Example 'kinds' might
            be, but are not limited to 'file', 'directory', 'object',
            'keyword argument'.
        """
        # preprocess line to create a CompletionEvent
        # call all of the matchers
        # merge their results, and for each merged set of completions,
        # listify and sort it before returning it.
        pass


class BaseMatcher(object):
    __metaclass__ = abc.ABCMeta

    def exclusive(self):
        """Should the completions returned by this matcher be the *exclusive*
        matches displayed to the user?

        If this property is true, other when this matcher returns sucesfully,
        its results will be shown exclusively to the client. Other matches
        will be excluded. This is generally not required, but may be suitable
        for use in contexts in which highly specialized inputs are required
        by the user, and other inputs may be invalid.
        """
        return False

    @abc.abstractmethod
    def match(self, event):
        """Recommend matches for a tab-completion event

        Parameters
        ----------
        event : CompletionEvent
            The event contains information about the context, including
            the current line, etc.

        Returns
        -------
        completions : dict, {str -> set(str)}
            The returned completions shall be a dict, mapping the 'kind' of
            the completion to a set of the recommend strings.
        """
        pass


class CompletionEvent(object):
    """Container for information about a tab completion event

    Attributes
    ----------
    block : str
        The complete input block, upto the cursor position.
    lines : list
        The block, after splitting on newlines.
    split : list
        A list of strings, formed by splitting `block` on all readline
        delimiters.
    text : str
        The last element in `split`. For readline clients, all matches are
        expected to start with `text`.

    Properties
    ----------
    tokens : list
        A list of tokens formed by running the python tokenizer on `line`.
    """

    def __init__(self, block, splitter=None):
        """Create a CompletionEvent
        
        Parameters
        ----------
        block : str
            A block of text
        splitter : CompletionSplitter, optional
            Which splitter to use to split the line by a set of delimiters.
            If left unsupplied, we'll create a new default CompletionSplitter.
            Otherwise, you may pass in your own, perhaps using a different
            set of delimiters.
        """
        self.block = block
        self.lines = block.split(os.linesep)

        if splitter is None:
            splitter = CompletionSplitter()
        self.split = splitter.split_line(block)

    @property
    def tokens(self):
        if self._tokens is None:
            # process the line into tokens
            self._tokens = []
        return self._tokens


class CompletionSplitter(object):
    """An object to split an input line in a manner similar to readline.

    By having our own implementation, we can expose readline-like completion in
    a uniform manner to all frontends.  This object only needs to be given the
    line of text to be split and the cursor position on said line, and it
    returns the 'word' to be completed on at the cursor after splitting the
    entire line.

    What characters are used as splitting delimiters can be controlled by
    setting the `delims` attribute (this is a property that internally
    automatically builds the necessary regular expression)"""

    # Private interface

    # A string of delimiter characters.  The default value makes sense for
    # IPython's most typical usage patterns.
    _delims = DELIMS

    # The expression (a normal string) to be compiled into a regular expression
    # for actual splitting.  We store it as an attribute mostly for ease of
    # debugging, since this type of code can be so tricky to debug.
    _delim_expr = None

    # The regular expression that does the actual splitting
    _delim_re = None

    def __init__(self, delims=None):
        delims = CompletionSplitter._delims if delims is None else delims
        self.delims = delims

    @property
    def delims(self):
        """Return the string of delimiter characters."""
        return self._delims

    @delims.setter
    def delims(self, delims):
        """Set the delimiters for line splitting."""
        expr = '[' + ''.join('\\'+ c for c in delims) + ']'
        self._delim_re = re.compile(expr)
        self._delims = delims
        self._delim_expr = expr

    def split_line(self, line, cursor_pos=None):
        """Split a line of text with a cursor at the given position.
        """
        l = line if cursor_pos is None else line[:cursor_pos]
        return self._delim_re.split(l)[-1]


