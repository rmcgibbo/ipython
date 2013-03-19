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

from IPython.core.inputsplitter import ESC_MAGIC
from IPython.core.completer2 import BaseCompleter

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class MagicsCompleter(BaseCompleter):
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
