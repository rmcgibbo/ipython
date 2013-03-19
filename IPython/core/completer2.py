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
import sys
import re
from collections import defaultdict

from IPython.config.configurable import Configurable
from IPython.utils.traitlets import CBool, Instance, MetaHasTraits, List
from IPython.utils.tokens import tokenize

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

DELIMS = ' \t\n`!@#$^&*()=+[{]}\\|;:\'",<>?'
GREEDY_DELIMS = ' =\r\n'

# Public API
__all__ = ['CompletionManager', 'BaseCompleter']

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class CompletionManager(Configurable):
    """Main entry point for the tab completion system. Here, you can register
    new completer classes, and ask for the completions on a block of text.
    """

    shell = Instance('IPython.core.interactiveshell.InteractiveShellABC')

    registry = List

    greedy = CBool(False, config=True, help="""
        Activate greedy completion

        This will enable completion on elements of lists, results of function
        calls, etc., but can be unsafe because the code is actually evaluated
        on TAB.""")

    debug = CBool(True, help="""
        In debug mode, we'll display tracebacks when completers fail.""")

    def _greedy_changed(self, name, old, new):
        """update the splitter and readline delims when greedy is changed"""
        if new:
            self.splitter.delims = GREEDY_DELIMS
        else:
            self.splitter.delims = DELIMS

    def __init__(self, shell, config=None, **kwargs):
        self.splitter = CompletionSplitter()
        self.shell = shell
        super(CompletionManager, self).__init__(config=config, **kwargs)

    def register(self, *completer_objects):
        """Register one or more new completers

        Each completer should be either be a subclass or instance of
        a subclass of BaseCompleter.

        If classes are given, they will be instantiated with the default
        constructor.  If your classes need a custom constructor, you should
        instanitate them first and pass the instance.
        """

        for m in completer_objects:
            if type(m) in (type, MetaHasTraits):
                # If we're given an uninstantiated class
                m = m(shell=self.shell, config=self.config)

            if isinstance(m, BaseCompleter):
                if m.exclusive:
                    # for efficiency, put exclusive completers at the beginning
                    # of the completers list.
                    self.registry.insert(0, m)
                else:
                    self.registry.append(m)
                m._set_completion_manager(self)
            else:
                raise TypeError('%s object is not an instance of '
                                'BaseCompleter' % type(m))


    def _completer_exclusive_changed(self, completer):
        """Notify the CompletionManager that one of its completer has changed
        its exclusivity policy.
        """

        if completer not in self.registry:
            raise ValueError('the completer being notified on is not registered')
        # re-insert it into the list of completers
        self.registry.remove(completer)
        self.register(completer)

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
        event = CompletionEvent(block[:cursor_position], self, self.splitter)
        collected_matches = defaultdict(lambda: set([]))

        for completer in self.registry:
            try:
                these_matches = completer.match(event)
            except:
                # Show the ugly traceback if the completer causes an
                # exception, but do NOT crash the kernel!
                if self.debug:
                    sys.excepthook(*sys.exc_info())

            if completer.exclusive and (these_matches is not None) and \
                    (len(these_matches) > 0):
            # if the completer is `exclusive`, we ONLY return its results
                collected_matches = these_matches
                break

            if these_matches is not None:
                # merge these matches into the collected matches. for each
                # kind, we want to merge the sets of match strings. It is not
                # possible for there to be two semantically different matches
                # that are the same kind and the same match string, so the
                # uniqueifying aspect of the set update is appropriate
                for kind, v in these_matches.iteritems():
                    if len(v) > 0:
                        collected_matches[kind].update(v)

        return dict((kind, sorted(v)) for kind, v in collected_matches.items())


class RLCompletionManager(CompletionManager):
    """A readline version of the CompletionManager"""

    active = CBool(True, help="""
        Activate the readline tab completion system.""")

    def __init__(self, shell, config=None):
        import IPython.utils.rlineimpl as readline

        self.readline = readline
        term = os.environ.get('TERM', 'xterm')
        self.dumb_terminal = term in ['dumb', 'emacs']

        # this is the buffer where readline flattened completions are held
        # between calls by the readline module to the rlcomplete method
        self._completions = None

        super(RLCompletionManager, self).__init__(shell=shell, config=config)

    def _greedy_changed(self, name, old, new):
        super(RLCompletionManager, self)._greedy_changed(name, old, new)
        if self.readline:
            self.readline.set_completer_delims(self.splitter.delims)

    def rlcomplete(self, text, state):
        """Return the state-th possible completion for 'text'.

        This is called successively with state == 0, 1, 2, ... until it
        returns None.  The completion should begin with 'text'.

        Parameters
        ----------
        text : string
            Text to perform the completion on.

        state : int
            Counter used by readline.
        """
        if state == 0:
            line_buffer = self.readline.get_line_buffer()
            cursor_position = self.readline.get_endidx()

            # merge the completions of each kind together into a
            # a single sorted list, with no duplicates
            c = self.complete(line_buffer, cursor_position)
            # this is supposed to be the fasted way to flatten the lists,
            # RE http://stackoverflow.com/questions/952914
            self._completions = sorted(set([e for lst in c.values() for e in lst]))

            # if there is only a tab on a line with only whitespace, instead of
            # the mostly useless 'do you want to see all million completions'
            # message, just do the right thing and give the user his tab!
            # Incidentally, this enables pasting of tabbed text from an editor
            # (as long as autoindent is off).

            # It should be noted that at least pyreadline still shows file
            # completions - is there a way around it?

            # don't apply this on 'dumb' terminals, such as emacs buffers, so
            # we don't interfere with their own tab-completion mechanism.

            if not (self.dumb_terminal or line_buffer.strip()):
                self.readline.insert_text('\t')
                sys.stdout.flush()
                return None

        try:
            return self._completions[state]
        except IndexError:
            return None


class BaseCompleter(Configurable):
    """Abstract base class to be subclasses by all completers.
    """

    shell = Instance('IPython.core.interactiveshell.InteractiveShellABC')
    __completion_manager = Instance('IPython.core.completer2.CompletionManager')

    exclusive = CBool(False, help="""
        Should the completions returned by this completer be the *exclusive*
        matches displayed to the user?

        If this property is true, other when this completer returns more than
        one match, its results will be shown exclusively to the client. Other
        matches will be excluded. This is suitable for specialized completers
        that only respond in a limited context. For example, the completer
        that is activated when the user types "import <TAB>" displays its
        results exclusively to the user, since other completions in that
        circumstance are not appropriate.""")

    str_key = Unicode('', help="""
        Only invoke the completer when the line begins with this key. For
        example, this feature may be used by the custom completer for the
        `cd` command to only respond when the line begins with `cd`. If the
        (default) empty string is used, the completer will be invoked on
        every tab event, and can manually check the CompletionEvent,
        returning `None` if it elects not to recommend any completions.""")

    re_key = Unicode('', help="""
        Only invoke the completer when the line matches this regular
        expression. If the (default) empty string is used, no regex matching
        will be performed, the completer will be invoked on every tab event.
        The completer can manually check the `CompletionEvent`, returning
        `None` if it elects not to recommend any completions.""")

    filter_results = Bool(True, help="""
        Filter the results returned by this matcher, only retaining those
        that begin with the string in the `text` attribute of the supplied
        completion event. This ensures, for example, that the matcher
        returns a set of strings, e.g. 'foo' and 'bar', and the user has
        typed an 'f', only the 'foo' match will be displayed.

        Note: in situations that require more complicated line parsing that
        simply the split on readline delimiters, it is appropriate to turn
        this option off.""")

    def _exclusive_changed(self, name, old, new):
        """Notify the manager that the exclusivity of this completer has
        changed"""
        if new != old and self.__completion_manager is not None:
            self.__completion_manager._completer_exclusive_changed(self)

    def _set_completion_manager(self, manager):
        self.__completion_manager = manager

    def __init__(self, shell, config=None):
        super(BaseCompleter, self).__init__(config=config)
        self.shell = shell

    def match(self, event):
        """Recommend matches for a tab-completion event

        Parameters
        ----------
        event : CompletionEvent
            The event contains information about the context, including
            the current line, etc.

        Returns
        -------
        completions : dict, {str -> set(str)}, or None
            The returned completions shall be a dict, mapping the 'kind' of
            the completion to a set of the recommend strings. The return value
            may also be None, to indicate that no matches were found.
        """
        raise NotImplementedError('This method should be implemented by subclasses')


class CompletionEvent(object):
    """Container for information about a tab completion event

    Attributes
    ----------
    block : str
        The complete input block, upto the cursor position.
    lines : list of str
        The block, after splitting on newlines.
    line : str
        The last line
    split : list of str
        A list of strings, formed by splitting `block` on all readline
        delimiters. Note: the split does not preserve the delimiters, so if
        you concatenate the split back together, you will not recreate the
        line. For example, if the line is ' hello {} world', split will
        be ['hello', 'world']. However, if the line ENDS in a delimiter,
        that will be part of the split, as an empty string at the end.
    text : str
        The last element in `split`. For readline clients, all matches are
        expected to start with `text`.
    manager : CompletionManager
        A pointer to the completion manager that dispatched this event

    Properties
    ----------
    tokens : list
        A list of tokens formed by running the python tokenizer on `line`.
    """

    def __init__(self, block, manager, splitter=None):
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
        self.manager = manager

        if splitter is None:
            splitter = CompletionSplitter()
        self.split = splitter.split(block)

        self.text = self.split[-1]
        self.line = self.lines[-1]

        self._tokens = None

    @property
    def tokens(self):
        if self._tokens is None:
            # process the line into tokens
            self._tokens = tokenize(self.block)
        return self._tokens

    def __repr__(self):
        return '<CompletionEvent: %s>' % str(self.__dict__)


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
        splits = self._delim_re.split(block)
        non_redundant = [e for e in splits if len(e) > 0]
        if splits[-1] == '':
            non_redundant.append('')
        return non_redundant
