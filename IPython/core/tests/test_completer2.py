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
from IPython.core.completerlib2 import (GlobalMatcher, AttributeMatcher,
    FileMatcher, MagicsMatcher, AliasMatcher, KeywordArgMatcher)

#-----------------------------------------------------------------------------
# Tests
#-----------------------------------------------------------------------------

def func1(long_argument_name=1, argument_name2=False):
    pass

def test_1():
    cm = CompletionManager()
    #cm.greedy = True
    ab = 10
    cm.register_matcher(GlobalMatcher())
    cm.register_matcher(AttributeMatcher())
    cm.register_matcher(FileMatcher())
    cm.register_matcher(MagicsMatcher())
    cm.register_matcher(AliasMatcher())
    cm.register_matcher(KeywordArgMatcher())

    words = ['a', 'test_1.', 'nonexistant.d', '~/', 'l', 'func1(l']
    for word in words:
        print '\n%s' % word
        print cm.complete(word)

    
test_1()