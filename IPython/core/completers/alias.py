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

import os

from IPython.core.completer2 import BaseCompleter

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class AliasCompleter(BaseCompleter):
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
