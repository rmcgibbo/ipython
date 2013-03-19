# encoding: utf-8
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
import sys
import imp
import re
from time import time
from zipimport import zipimporter
import inspect

from IPython.utils.traitlets import CBool
from IPython.core.completer2 import BaseCompleter

#-----------------------------------------------------------------------------
# Globals and constants
#-----------------------------------------------------------------------------

# Time in seconds after which the rootmodules will be stored permanently in the
# ipython ip.db database (kept in the user's .ipython dir).
TIMEOUT_STORAGE = 2

# Time in seconds after which we give up
TIMEOUT_GIVEUP = 20

# Regular expression for the python import statement
import_re = re.compile(r'(?P<name>[a-zA-Z_][a-zA-Z0-9_]*?)'
                       r'(?P<package>[/\\]__init__)?'
                       r'(?P<suffix>%s)$' %
                       r'|'.join(re.escape(s[0]) for s in imp.get_suffixes()))

# RE for the ipython %run command (python + ipython scripts)
magic_run_re = re.compile(r'.*(\.ipy|\.py[w]?)$')

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class ModuleCompleter(BaseCompleter):
    """Completions after user has typed 'import ...' or 'from ...'

    'import xml.d'
    'from xml.dom import'
    """
    exclusive = CBool(True)

    def match(self, event):
        """On the tab event, we fire off a call to find all the importable
        modules/classes/names given the current context (all_matches) and
        then return a subset, based on `event.text`.
        """

        unfiltered_matches = self.all_matches(event)
        if unfiltered_matches is not None:
            return {'import': set([e for e in unfiltered_matches if
                e.startswith(event.text)])}
        return None

    def all_matches(self, event):
        """Find all of the possible matches for a certain line.

        This method will not do filtering based on event.text

        Returns
        -------
        names : list
            A list of strings of possible completions, including modules and
            classes that can be imported
        """



        # if the line reads 'from xml.d import', we'll have the split
        # as ['from', 'xml.d', 'import']
        n_words = len(event.split)

        # only respond then the first word on the line is
        # "from" or "import"
        if n_words == 1 or (event.split[0] not in ['from', 'import']):
            return None

        # if the user has typed 'from xml.d <TAB>'
        if (n_words == 3) and (event.split[0] == 'from') and \
                ('import'.startswith(event.text)):
            return ['import ']

        modules = event.split[1].split('.')
        if n_words < 3:
            if n_words == 2 and event.text == '':
                # if the user has only typed 'import ' or 'from '
                return root_modules(self.shell.db)
            if len(modules) < 2:
                return root_modules(self.shell.db)

            # if the user has typed 'import scipy.spatial.d<TAB>', we try
            # importing everything from scipy.spatial
            completion_list = try_import('.'.join(modules[:-1]),
                                         only_modules=True)

            return ['.'.join(modules[:-1] + [el]) for el in completion_list]

        elif event.split[0] == 'from':
            return try_import(event.split[1], only_modules=False)


#-----------------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------------


def module_list(path):
    """
    Return the list containing the names of the modules available in the given
    folder.
    """
    # sys.path has the cwd as an empty string, but isdir/listdir need it as '.'
    if path == '':
        path = '.'

    # A few local constants to be used in loops below
    pjoin = os.path.join

    if os.path.isdir(path):
        # Build a list of all files in the directory and all files
        # in its subdirectories. For performance reasons, do not
        # recurse more than one level into subdirectories.
        files = []
        for root, dirs, nondirs in os.walk(path):
            subdir = root[len(path)+1:]
            if subdir:
                files.extend(pjoin(subdir, f) for f in nondirs)
                dirs[:] = []  # Do not recurse into additional subdirectories.
            else:
                files.extend(nondirs)

    else:
        try:
            files = list(zipimporter(path)._files.keys())
        except:
            files = []

    # Build a list of modules which match the import_re regex.
    modules = []
    for f in files:
        m = import_re.match(f)
        if m:
            modules.append(m.group('name'))
    return list(set(modules))


def root_modules(database=None):
    """Retrieve a list of the names of all the modules available in
    the PYTHONPATH

    Parameters
    ----------
    database : dict-like
        To improve responsiveness, the results of this method are cached
        in the ipython database.

    Returns
    -------
    names : list of string
        A list of all the names that are importable via `import <whatever>`
    """

    if database and 'rootmodules' in database:
        return database['rootmodules']

    t = time()
    store = False
    modules = list(sys.builtin_module_names)
    for path in sys.path:
        modules += module_list(path)
        if time() - t >= TIMEOUT_STORAGE and not store:
            store = True
            print("\nCaching the list of root modules, please wait!")
            print("(This will only be done once - type '%rehashx' to "
                  "reset cache!)\n")
            sys.stdout.flush()
        if time() - t > TIMEOUT_GIVEUP:
            print("This is taking too long, we give up.\n")
            if database:
                database['rootmodules'] = []
            return []

    modules = set(modules)
    if '__init__' in modules:
        modules.remove('__init__')
    modules = list(modules)

    if store and database:
        database['rootmodules'] = modules

    return modules


def try_import(mod, only_modules=False):
    """Find all of the importable submodules, functions, etc inside of
    a given module

    Parameters
    ----------
    mod : str
        The name of the base module
    only_modules : bool, optional
        Only look for modules. When False, we'll also look for functions,
        classes, etc inside of `mod`.

    Returns
    -------
    names : list of strings
        The names that can be imported from within `mod`.
    """

    try:
        m = __import__(mod)
    except:
        return []
    mods = mod.split('.')
    for module in mods[1:]:
        m = getattr(m, module)

    m_is_init = hasattr(m, '__file__') and '__init__' in m.__file__

    completions = []
    if (not hasattr(m, '__file__')) or (not only_modules) or m_is_init:
        completions.extend([attr for attr in dir(m) if
                            is_importable(m, attr, only_modules)])

    completions.extend(getattr(m, '__all__', []))
    if m_is_init:
        completions.extend(module_list(os.path.dirname(m.__file__)))
    completions = set(completions)
    if '__init__' in completions:
        completions.remove('__init__')
    return list(completions)


def is_importable(module, attr, only_modules):
    if only_modules:
        return inspect.ismodule(getattr(module, attr))
    else:
        return not(attr[:2] == '__' and attr[-2:] == '__')
