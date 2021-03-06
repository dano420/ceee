#!/bin/env python
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generates a file with MOCK_METHODX(...) macros for a COM interface.

For interfaces that will not change, you can run this file by hand.  For
interfaces that may still change, you could run it as part of your build
system to generate code, then #include the generated list of methods inside an
appropriate wrapper class.

Usage:
  com_mock.py INTERFACE_NAME HEADER [ADD_HEADERS]* > output-inl.h
"""

import re
import sys

# Finds an interface block in a header file generated by IDL.
_INTERFACE_PATTERN = (r'MIDL_INTERFACE\("[A-Za-z0-9\-]+"\)\s*%s\s*:\s*'
                      r'public\s*(?P<base>\w+)\s*{\s*public:'
                      r'(?P<method_block>[^}]+)};')

# Parses out a method from within an interface block.
_METHOD_RE = re.compile(r'virtual\s*(:?/\*[^*]+\*/)?\s*(?P<ret>\w+)\s*'
                        r'STDMETHODCALLTYPE\s*(?P<name>\w+)\s*\('
                        r'(?P<params>[^\)]+)\)\s*=\s*0;')

# Finds inline C-style comments.
_COMMENTS_RE = re.compile('/\*.*?\*/')

# Finds __RPC_xyz defines.
_RPC_RE = re.compile(' __RPC\w*')

# Finds whitespace.
_WHITESPACE_RE = re.compile('\s+')

# Finds default argument values.
_DEFAULT_ARG_RE = re.compile('\s*=\s*[^,]*')

# Header for generated files.
_FILE_HEADER = '''\
// Copyright (c) 2010 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Auto-generated by com_mock.py

'''

class Mocker(object):
  """Given a set of header files, can generate mocky goodness for interfaces
  defined in them.
  """

  def __init__(self):
    self.headers_ = ''

  def AddHeaders(self, header_files):
    """Adds the specified files to the headers to parse."""
    assert header_files
    # Slurp all the header files into a single huge big string.
    # Yummy nonperformant code - but it probably doesn't need to be.
    headers = []
    for f in header_files:
      fo = open(f, 'r')
      headers.append(fo.read())
      fo.close()
    self.headers_ += '\n'.join(headers)

  def _GetInterfaceInfo(self, interface_name):
    """Returns a tuple (base_interface, method_block) or None."""
    m = re.search(_INTERFACE_PATTERN % interface_name, self.headers_)
    if m:
      return (m.group('base'), m.group('method_block'))
    else:
      return None

  @staticmethod
  def _ProcessParams(params):
    """Return a tuple (count, cleaned_up_params)."""
    if params == ' void':
      return (0, '')
    else:
      params = params.replace('\n', ' ')
      params = _COMMENTS_RE.sub('', params)
      params = _RPC_RE.sub(' ', params)
      params = _WHITESPACE_RE.sub(' ', params)
      params = _DEFAULT_ARG_RE.sub(' ', params)
      return (params.count(',') + 1, params.strip())

  def _MockMethodsInBlock(self, block):
    """Return a list of mock functions for each of the methods defined
    in 'block', which is the text between 'public:' and '};' in an interface
    definition.
    """
    methods = []
    for m in _METHOD_RE.finditer(block):
      return_type = m.group('ret')
      name = m.group('name')
      params = m.group('params')
      (param_count, clean_params) = self._ProcessParams(params)

      method_definition = ('MOCK_METHOD%d_WITH_CALLTYPE(__stdcall, %s, %s(%s));'
                           % (param_count, name, return_type, clean_params))
      if len(method_definition) > 78:
        method_definition = (
            'MOCK_METHOD%d_WITH_CALLTYPE(__stdcall, %s, %s(\n    %s));' %
            (param_count, name, return_type, clean_params))
      methods.append(method_definition)
    return methods

  def MockInterface(self, name):
    """Returns a list of all the mock methods needed for the given
    interface (including methods from inherited interfaces, but stopping
    short of IDispatch and IUnknown).
    """
    info = self._GetInterfaceInfo(name)
    if not info:
      return ''

    # Generate inherited methods
    methods = []
    if info[0] not in ('IUnknown', 'IDispatch'):
      methods.extend(self.MockInterface(info[0]))
    methods.extend(self._MockMethodsInBlock(info[1]))
    return methods


def MockMethods(interface_name, header_files):
  """Returns a string with a correctly filled-out MOCK_METHODX(...) line
  for each method in the given interface, plus all of its inherited interfaces,
  terminating when IDispatch or IUnknown is reached.

  You must list all header files required to find the interface itself and
  all of the interfaces it inherits from, except IDispatch and IUnknown.

  Header files must be IDL-generated for the pattern matching used in the
  code to work correctly.

  Args:
    interface_name: 'IWebBrowser2'
    header_files: ['c:\\platform_sdk\\files\\Include\\exdisp.h',
                   'c:\\platform_sdk\\files\\Include\\oaidl.h']

  Returns:
    'MOCK_METHOD1_WITH_CALLTYPE(__stdcall, GetWindow, HRESULT()); ...'
  """
  mocker = Mocker()
  mocker.AddHeaders(header_files)
  return '\n'.join(mocker.MockInterface(interface_name))


def Main(args):
  if not args or len(args) < 2:
    print __doc__
    return 1
  else:
    print _FILE_HEADER
    print MockMethods(args[0], args[1:])
    return 0


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
