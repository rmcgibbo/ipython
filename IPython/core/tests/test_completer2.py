# -*- coding: utf-8 -*-
"""Tests for completer2

"""
from __future__ import absolute_import

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import os
import shutil
import sys
import tempfile
import unittest
from os.path import join

import nose.tools as nt
from nose import SkipTest

from IPython.core.completer2 import CompletionManager
from IPython.core.completerlib2 import GlobalMatcher, AttributeMatcher, FileMatcher

#-----------------------------------------------------------------------------
# Tests
#-----------------------------------------------------------------------------



def test_1():
    cm = CompletionManager()
    #cm.greedy = True
    cm.register_matcher(GlobalMatcher())
    cm.register_matcher(AttributeMatcher())
    cm.register_matcher(FileMatcher())

    print cm.complete('a')
    print cm.complete('test_1.')
    print cm.complete('nonexistant.d')
    print cm.complete('~/')
    
test_1()