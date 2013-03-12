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
import re
import abc
from collections import defaultdict

from IPython.config.configurable import Configurable
from IPython.utils.tokens import tokenize

# Public API
__all__ = ['CompletionManager', 'BaseMatcher']

DELIMS = ' \t\n`!@#$^&*()=+[{]}\\|;:\'",<>?'
GREEDY_DELIMS = ' =\r\n'

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class CompletionManager(Configurable):
    """Main entry point for the tab completion system. Here, you can register
    new matcher classes, and ask for the completions on a block of text.
    """
    
    def __init__(self, config=None, **kwargs):
        self.splitter = CompletionSplitter()
        self.matchers = []
        
        super(CompletionManager, self).__init__(config=config, **kwargs)
        # self.exclusive_matchers = []

    def register_matcher(self, matcher):
        """Register a new matcher
        """
        if isinstance(matcher, BaseMatcher):
            self.matchers.append(matcher)
        else:
            raise TypeError('%s object is not an instance of BaseMatcher' %
                            type(matcher))

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
            The keys of the completions dict are the 'kind' of the
            completion, which may be displayed in rich frontends. Example
            'kinds' might be, but are not limited to 'file', 'directory',
            'object', 'keyword argument'.
        """
        event = CompletionEvent(block[:cursor_position], self.splitter)
        collected_matches = defaultdict(lambda: set([]))

        for matcher in self.matchers:
            these_matches = matcher.match(event)
            if matcher.exclusive:
                collected_matches = these_matches
                break

            # merge these matches into the collected matches. for each
            # kind, we want to merge the sets of match strings. It is not
            # possible for there to be two semantically different matches
            # that are the same kind and the same match string, so the
            # uniqueifying aspect of the set update is appropriate
            for kind, v in these_matches:
                collected_matches[kind].update(v)

        return dict((kind, sorted(v)) for kind, v in collected_matches.items())


class BaseMatcher(object):
    """Abstract base class to be subclasses by all matchers.
    """
    
    __metaclass__ = abc.ABCMeta

    @property
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
        self.split = splitter.split(block)
        self._tokens = None

    @property
    def tokens(self):
        if self._tokens is None:
            # process the line into tokens
            self._tokens = tokenize(self.block)
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
        expr = '[' + ''.join('\\' + c for c in delims) + ']'
        self._delim_re = re.compile(expr)
        self._delims = delims
        self._delim_expr = expr

    def split(self, block):
        """Split a line of text with a cursor at the given position.
        """
        return self._delim_re.split(block)
