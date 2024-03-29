#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: __init__.py 106448 2017-02-14 01:51:54Z carlos.sanchez $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.dataserver')

#: User notification settings
NOTIFICATION_SETTINGS_ANNOTATION_KEY = u'MAIL_NOTIFICATION_SETTINGS'
