#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: traversal.py 106445 2017-02-14 00:54:23Z carlos.sanchez $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.messaging.interfaces import IMailbox


@interface.implementer(IPathAdapter)
def _mailbox_path_adapter(user, request):
    return IMailbox(user)
