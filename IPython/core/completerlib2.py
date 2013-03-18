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

import re
import __builtin__
import keyword
from collections import defaultdict

from IPython.core.completer2 import BaseMatcher
from IPython.utils.dir2 import dir2
from IPython.utils.traitlets import CBool, Enum

#-----------------------------------------------------------------------------
# Functions
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
        
        matches = defaultdict(lambda : set())
        n = len(event.text)
        for kind, lst in (('keywords', keyword.kwlist),
                          ('locals', event.manager.namespace.keys()),
                          ('bultins', __builtin__.__dict__)):
            for word in lst:
                if word[:n] == event.text and word != '__builtins__':
                    matches[kind].add(word)
                
        return matches

class AttributeMatcher(BaseMatcher):
    limit_to__all__ = CBool(default_value=False, config=True,
        help="""Instruct the completer to use __all__ for the completion
        
        Specifically, when completing on ``object.<tab>``.
        
        When True: only those names in obj.__all__ will be included.
        
        When False [default]: the __all__ attribute is ignored 
        """
    )
    
    omit__names = Enum((0,1,2), default_value=2, config=True,
        help="""Instruct the completer to omit private method names
        
        Specifically, when completing on ``object.<tab>``.
        
        When 2 [default]: all names that start with '_' will be excluded.
        
        When 1: all 'magic' names (``__foo__``) will be excluded.
        
        When 0: nothing will be excluded.
        """
    )
    
    attr_re = re.compile(r"(\S+(\.\w+)*)\.(\w*)$")
    greedy_attr_re = re.compile(r"(.+)\.(\w*)$")    

    def match(self, event):
        m1 = self.attr_re.match(event.text)
        if m1:
            expr, attr = m1.group(1, 3)
        elif event.manager.greedy:
            m2 = self.greedy_attr_re.match(event.line)
            if m2:
                expr, attr = m2.group(1,2)
            else:
                return None
        else:
            return None
            
        try:
            obj = eval(expr, event.manager.namespace)
        except:
            # raise
            return None
            
        words = dir2(obj)
        
        if self.limit_to__all__ and hasattr(obj, '__all__'):
            try:
                words = [w for w in getattr(obj, '__all__') if isinstance(w,
                    basestring)]
            except:
                return None
        else: 
            words = dir2(obj)
        
        try:
            words = generics.complete_object(obj, words)
        except:
            pass
            
        
        if event.text.endswith('.') and self.omit__names:
            if self.omit__names == 1:
                # filter out matches like __stuff__
                words = [w for w in words if not w.startswith('__') and
                    w.endswith('__')]
            else:
                # filter out any match that starts with '_'
                words = [w for w in words if not w.startswith('_')]
        
        n = len(attr)
        res = ["%s.%s" % (expr, w) for w in words if w[:n] == attr]
        return {'attributes': set(res)}
