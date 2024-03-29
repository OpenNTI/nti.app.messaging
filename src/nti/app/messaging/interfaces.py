#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: interfaces.py 106436 2017-02-13 23:05:46Z carlos.sanchez $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.security.interfaces import IPrincipal

from nti.messaging.interfaces import IMessage
from nti.messaging.interfaces import IMessageBase
from nti.messaging.interfaces import IReceivedMessageNotifier

from nti.schema.field import Bool
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ListOrTuple
from nti.schema.field import Text as ValidText


class ISummarized(interface.Interface):

    Summary = ValidText(title="Summary of the object")


class IMessageSummary(IMessageBase, ISummarized):
    pass


class IEmailMessageNotifier(IReceivedMessageNotifier):
    pass


class IMessageNotificationSettings(interface.Interface):

    SendEmail = Bool(title="Whether to send ", default=True)

    def notifiers_for_message(recv_msg):
        """
        List of notifiers to used based on received message 
        and notification settings
        """
        pass


class IConversation(interface.Interface):

    RootMessage = Object(IMessage,
                         title="The root message in the thread",
                         required=False)
    RootMessage.setTaggedValue('_ext_excluded_out', True)

    MostRecentMessage = Object(IMessage,
                               title="The most recent message in the thread",
                               required=False)

    UnOpenedCount = Number(title="The number of unopended IMessage objects in the thread",
                           required=False,
                           min=0)

    Participants = ListOrTuple(title="Anyone that has participated in this conversation at some point in time",
                               value_type=Object(IPrincipal),
                               required=False)


class IConversationProvider(interface.Interface):
    """
    An object capable of producing IConversation objects
    """

    def conversations(user=None):
        """
        Return an iterable of IConversation objects
        """
