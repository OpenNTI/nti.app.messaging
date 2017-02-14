#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: install.py 106171 2017-02-09 19:04:42Z carlos.sanchez $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 1

from zope import interface

from zope.generations.generations import SchemaManager as BaseSchemaManager

from zope.generations.interfaces import IInstallableSchemaManager

from zope.intid.interfaces import IIntIds

from nti.messaging.index import install_messaging_catalog


@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """

    def __init__(self):
        super(_SchemaManager, self).__init__(
            generation=generation,
            minimum_generation=generation,
            package_name='nti.app.messaging')

    def install(self, context):
        evolve(context)


def evolve(context):
    conn = context.connection
    root = conn.root()
    dataserver_folder = root['nti.dataserver']
    lsm = dataserver_folder.getSiteManager()
    intids = lsm.getUtility(IIntIds)
    install_messaging_catalog(dataserver_folder, intids)
