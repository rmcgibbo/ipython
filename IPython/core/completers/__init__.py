"""Implementations of the tab completion routines in IPython
"""
#-----------------------------------------------------------------------------
#  Copyright (c) 2013 The IPython Development Team.
#
#  Distributed under the terms of the Modified BSD License.
#
#  The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------


from .alias import AliasCompleter
from .objects import GlobalCompleter, AttributeCompleter
from .filesystem import FileCompleter, CDCompleter, ShellLineCompleter
from .kwargs import KeywordArgCompleter
from .magics import MagicsCompleter
from .modules import ModuleCompleter
