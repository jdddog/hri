# Copyright (c) 2011 Robert Smallshire

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

'''Selector functions and selector function factories.'''

import operator

from .portability import is_callable
from .types import is_string


__author__ = 'Robert Smallshire'

k_ = operator.itemgetter
'''Create a selector function which indexes into the element by key.

The callable object returned by this function fetches one or more items from
its only operand using the operand's __getitem__() method. If multiple items
are specified a tuple of looked-up values will be returned.

Args:
    key: The key which the generated selector will use to index into
        elements.

    *args: Optional additional arguments which will be used as additional keys
        for lookup.  If supplied then the created selector will return a tuple
        of values.

Returns:
    A unary selector function which indexes into its only argument with
    the supplied key value(s).
'''


a_ = operator.attrgetter
'''Create a selector function which selects an attribute by name.

The callable object returned by this function fetches one or more
attributes from its only operand using the operand's __getitem__() method.
If multiple items are specified a tuple of retrieved attribute values will
be returned.

Args:
    name: The name of the attribute which will be retrieved from each
        element. The attribute name may contain dots which will be resolved
        through sequential attribute lookups.

    *args: Optional additional attribute names which will be used as
    additional attribute names for lookup.  If supplied then the created
    selector will return a tuple of values. The attribute name may contain
    dots which will be resolved through sequential attribute lookups.

Returns:
    A unary selector function which retrieves the named attribute(s) from
    its only argument and returns the value(s) of those attribute(s).
'''


m_ = operator.methodcaller
'''Create a selector function which calls a named method.

Args:
    name: The name of the method which will be called on each element.

    *args: Any optional positional arguments which will be passed to the
        called method.

    **kwargs: Any optional named arguments which will be passed to the
        called method.

Returns:
    A unary selector function which calls the named method with any
    optional positional or named arguments and which returns the
    result of the method call.
'''

k_ = operator.itemgetter
'''Create a selector function which indexes into the element by key.

The callable object returned by this function fetches one or more items from
its only operand using the operand's __getitem__() method. If multiple items
are specified a tuple of looked-up values will be returned.

Args:
    key: The key which the generated selector will use to index into
        elements.

    *args: Optional additional arguments which will be used as additional keys
        for lookup.  If supplied then the created selector will return a tuple
        of values.

Returns:
    A unary selector function which indexes into its only argument with
    the supplied key value(s).
'''

def make_selector(value):
    '''Create a selector callable from the supplied value.

    Args:
        value: If is a callable, then returned unchanged.  If a string is used
            then create an attribute selector. If in an integer is used then
            create a key selector.

    Returns:
        A callable selector based on the supplied value.
try:
    # Python 2
    basestring()
    def is_string(s):
        return isinstance(s, basestring)
except NameError:
    # Python 3
    def is_string(s):
        return isinstance(s, str)

    Raises:
        ValueError: If a selector cannot be created from the value.
    '''
    if is_callable(value):
        return value
    if is_string(value):
        return a_(value)
    raise ValueError("Unable to create callable selector from '{0}'".format(value))



def identity(x):
    '''The identity function.

    The identity function returns its only argument.

    Args:
        x: A value that will be returned.

    Returns:
        The argument x.
    '''
    return x
