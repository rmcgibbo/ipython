# encoding: utf-8
"""
Utilities for tokenizing source code and processesing those tolens
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2012  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import StringIO
import tokenize as _tokenizelib

#-----------------------------------------------------------------------------
# Code
#-----------------------------------------------------------------------------

def tokenize(src):
    """Tokenize a block of python source code using the stdlib's tokenizer.

    Parameters
    ----------
    src : str
        A string of potential python source code. The code isn't evaled, it's
        just split into its representive tokens

    Returns
    -------
    tokens : list of strings
        A list of tokens. Tokenizer errors from invalid python source (like
        unclosed string delimiters) are supressed.

    Examples
    --------
    In [1]: tokenize('a + b = ["cdefg" + 10]')
    ['a', '+', 'b', '=', '[', '"cdefg"', '+', '10', ']']

    Notes
    -----
    This serves a similar function to simply splitting the source on delmiters
    (as done by CompletionSplitter) but is slightly more sophisticated. In
    particular, characters that are delmiters are never returned in the tokens
    by CompletionSplitter (or its regular expression engine), so something
    like this happens:

    In[2]: a = CompletionSplitter()._delim_re.split('a+ "hello')
    In[3]: b = CompletionSplitter()._delim_re.split('a+= hello')
    In[4]: a == b
    True

    This makes it very tricky to do complicated types of tab completion.

    This tokenizer instead uses the stdlib's tokenize, which is a little
    bit more knowledgeable about python syntax. In particular, string literals
    e.g. `tokenize("'a' + '''bc'''") == ["'a'", "+", "'''bc'''"]` get parsed
    as single tokens.
    """
    raw_str = StringIO.StringIO(src)
    itoks = _tokenizelib.generate_tokens(raw_str.readline)
    def run():
        try:
            for toktype, toktext, (srow, scol), (erow, ecol), line  in itoks:
                if toktype != _tokenizelib.ENDMARKER:
                    yield toktext
        except _tokenizelib.TokenError:
            pass
    tokens = list(run())
    return tokens
