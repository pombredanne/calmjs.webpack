# -*- coding: utf-8 -*-
"""
A collection of helpers for manipulating ES5 sources.
"""

from __future__ import unicode_literals

from calmjs.parse.asttypes import Array
from calmjs.parse.asttypes import Assign
from calmjs.parse.asttypes import DotAccessor
from calmjs.parse.asttypes import FunctionCall
from calmjs.parse.asttypes import Arguments
from calmjs.parse.asttypes import Identifier
from calmjs.parse.asttypes import String

from calmjs.parse.unparsers.es5 import definitions
from calmjs.parse.unparsers.base import BaseUnparser
from calmjs.parse.walkers import ReprWalker
from calmjs.parse import rules

from calmjs.webpack.base import DEFAULT_CALMJS_EXPORT_NAME
from calmjs.webpack.interrogation import walker
from calmjs.webpack.walkers import ReplacementWalker

replacer = ReplacementWalker()
repr_ = ReprWalker().walk


def _non_asttypes_string(arg):
    if isinstance(arg, String):
        return False

    # first check whether AMD syntax is used
    if isinstance(arg, Array):
        return any(filter(lambda n: not isinstance(n, String), arg))
    # otherwise this is assumed to be dynamic.
    return True


def extract_dynamic_require(node):
    """
    Return require() function calls that have one or more non-static
    arguments (i.e. first argument not String).
    """

    return walker.filter(node, lambda n: (
        isinstance(n, FunctionCall) and
        isinstance(n.identifier, Identifier) and
        n.identifier.value == 'require' and
        n.args.items and _non_asttypes_string(n.args.items[0])
    ))


def create_calmjs_require(node):
    """
    Replace the dynamic requires in the node with the calmjs version.
    """

    # node is a FunctionCall
    # TODO the source map related attributes may need to be copied over
    # from the existing FunctionCall  node.
    return FunctionCall(
        args=node.args,
        identifier=DotAccessor(
            node=FunctionCall(
                args=Arguments([String("'%s'" % DEFAULT_CALMJS_EXPORT_NAME)]),
                identifier=Identifier(value='require'),
            ),
            # preserve the original identifier within the DotAccessor itself
            identifier=node.identifier,
        )
    )


def convert_dynamic_require(tree):
    """
    Take the given tree, generate a conversion table and apply the
    transformation in-place in the tree.  Also return the tree.
    """

    nodemap = {
        node: create_calmjs_require(node)
        for node in extract_dynamic_require(tree)
    }
    replacer.replace(tree, nodemap)
    return tree


def convert_dynamic_require_hook(dispatcher, tree):
    """
    Turn this into unparser compatible prewalk hook, by taking the
    dispatcher argument.
    """

    return convert_dynamic_require(tree)


def convert_dynamic_require_unparser(indent_str='    '):
    """
    The dynamic require unparser.
    """

    return BaseUnparser(
        definitions=definitions,
        rules=(rules.indent(indent_str=indent_str),),
        prewalk_hooks=(convert_dynamic_require_hook,),
    )


def inject_array_items_to_object_property_value(object_, key, array):
    """
    Inject values specified in the array to the property in the object
    specified by the key, with the assumption that either the property
    in the object under that key is already an array or does not already
    exist.

    All arguments must be of the relevant subclass of asttypes.Node.
    """

    key_str = repr_(key)
    for property_ in object_.properties:
        if repr_(property_.left) == key_str:
            array.items.extend(property_.right.items)
            property_.right = array
            break
    else:
        # TODO if the actual asttypes module reference can be derived
        # from the provided objects, it should be used to resolve the
        # desired Assign type.
        object_.properties.append(Assign(left=key, op=':', right=array))
