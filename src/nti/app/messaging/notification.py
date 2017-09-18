#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"
logger = __import__('logging').getLogger(__name__)

import nameparser

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from pyramid.renderers import render

from pyramid.threadlocal import get_current_request

from zope.container.contained import Contained

from zope.schema.fieldproperty import createFieldProperties

from zope.security.interfaces import IPrincipal

from nti.app.messaging.interfaces import IEmailMessageNotifier
from nti.app.messaging.interfaces import IMessageNotificationSettings

from nti.appserver._table_utils import AbstractNoteContentProvider

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.users.users import User

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.mailer.interfaces import IEmailAddressable

from nti.schema.schema import SchemaConfigured

from nti.messaging.interfaces import IMailbox
from nti.messaging.interfaces import IMessage
from nti.messaging.interfaces import IPeerToPeerMessage
from nti.messaging.interfaces import IReceivedMessageNotifier

from nti.mailer.interfaces import ITemplatedMailer


@component.adapter(IUser, IMessage)
@interface.implementer(IMessageNotificationSettings)
class MessageNotificationSettings(SchemaConfigured,
                                  PersistentCreatedModDateTrackingObject,
                                  Contained):
    createFieldProperties(IMessageNotificationSettings)

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)
        PersistentCreatedModDateTrackingObject.__init__(self, **kwargs)

    def notifiers_for_message(self, recv_msg):
        if self.SendEmail:
            return (DefaultEmailNotifier(recv_msg.Message, IMailbox(recv_msg)), )


@component.adapter(IUser, IMessage)
@interface.implementer(IMessageNotificationSettings)
class AlwaysEmailNotificationSettings(Contained):

    SendEmail = True

    def __init__(self, user, message):
        pass

    def notifiers_for_message(self, recv_msg):
        notifier = component.queryMultiAdapter((recv_msg.Message, IMailbox(recv_msg)),
                                               IEmailMessageNotifier)
        return (notifier, ) if notifier else ()


@component.adapter(IMessage, IMailbox)
@interface.implementer(IEmailMessageNotifier)
class DefaultEmailNotifier(object):

    template = 'default-message'  # Simply directs user in the platform

    reply_to = None  # By default just let it go back to the sender

    def __init__(self, message, mailbox):
        self.message = message
        self.mailbox = mailbox

    def _name_web(self, user, **kwargs):
        return IFriendlyNamed(user).realname

    def _first_name(self, user, friendly=None):
        if not friendly:
            friendly = IFriendlyNamed(user, None)
        if friendly:
            human_name = nameparser.HumanName(friendly.realname)
            first_name = human_name.first
            if first_name:
                return first_name

    def _real_name(self, user, friendly=None):
        if not friendly:
            friendly = IFriendlyNamed(user, None)
        return friendly.realname if friendly else None

    def _informal_name(self, user, friendly=None, prefer_name_web=False):
        friendly = friendly if friendly else IFriendlyNamed(user, None)
        if prefer_name_web:
            options = (self._name_web, self._first_name, self._real_name)
        else:
            options = (self._first_name, self._name_web, self._real_name)

        for option in options:
            name = option(user, friendly=friendly)
            if name:
                return name

    def _template_info_for_user(self, user, prefer_name_web=False):
        friendly = IFriendlyNamed(user, None)
        data = {
            'informal_name': self._informal_name(user, 
                                                 friendly=friendly,
                                                 prefer_name_web=prefer_name_web)
        }
        return data

    def _template_args(self, recv_msg):
        receiver_principal = IPrincipal(self.mailbox.creator)
        receiver_user = User.get_user(receiver_principal.id)

        sender_principal = recv_msg.Message.From
        sender_user = User.get_user(sender_principal.id)

        # there are peer to peer so both these should be users
        if not sender_user or not receiver_user:
            __traceback_info__ = sender_user, receiver_user
            raise ValueError('Expected principals to be users')

        args = {
            'sender': self._template_info_for_user(sender_user, prefer_name_web=True),
            'receiver': self._template_info_for_user(receiver_user, prefer_name_web=True)
        }

        return args

    def _subject(self, recv_msg):
        return self.message.Subject

    def _email_for(self, principal):
        user = User.get_user(principal.id)
        addressable = IEmailAddressable(user, None)
        return addressable.email if addressable else None

    def _mailer_package(self):
        return 'nti.app.messaging'

    def _do_mailer(self, recv_msg, kallable):
        __traceback_info__ = (self.message.From, self.mailbox.creator, self._subject(recv_msg))
        from_email = self._email_for(self.message.From)
        to_email = self._email_for(IPrincipal(self.mailbox.creator))
        if not from_email or not to_email:
            logger.warn('Unable to obtain IEmailAddressable from sender (%s) or recipient (%s)', 
                        from_email, to_email)
            return

        args = self._template_args(recv_msg)
        return kallable(self.template,
                        subject=self._subject(recv_msg),
                        recipients=[to_email],
                        template_args=args,
                        reply_to=self.reply_to,
                        package=self._mailer_package(),
                        text_template_extension='.mak')

    def _create_mail_message(self, recv_msg):
        mailer = component.getUtility(ITemplatedMailer)
        return self._do_mailer(recv_msg, mailer.create_simple_html_text_email)

    def notify(self, recv_msg):
        self.send_email(recv_msg)

    def send_email(self, recv_msg):
        mailer = component.getUtility(ITemplatedMailer)
        return self._do_mailer(recv_msg, mailer.queue_simple_html_text_email)


@component.adapter(IMessage, IMailbox)
@interface.implementer(IReceivedMessageNotifier)
class ExternalNotifier(object):

    def __init__(self, message, mailbox):
        self.message = message
        self.mailbox = mailbox

    def notify(self, recv_msg):
        user = IUser(recv_msg)
        settings = component.getMultiAdapter((user, recv_msg.Message), 
                                             IMessageNotificationSettings)
        for note in settings.notifiers_for_message(recv_msg):
            note.notify(recv_msg)


class PeerToPeerContentProvider(AbstractNoteContentProvider):
    pass


@component.adapter(IPeerToPeerMessage, IMailbox)
class PeerToPeerEmailNotifier(DefaultEmailNotifier):

    template = 'templates/send_message'

    def _body_args(self, message):
        args = {'message': None, 'plain_text_message': None}
        content_provider = PeerToPeerContentProvider(message, None, None)
        if content_provider:
            args['message'] = content_provider.render()
        return args

    def _subject(self, recv_msg):
        subject = super(PeerToPeerEmailNotifier, self)._subject(recv_msg)
        if recv_msg.Message.references:
            subject = 'RE: ' + subject
        return subject

    def _template_args(self, recv_msg):
        args = super(PeerToPeerEmailNotifier, self)._template_args(recv_msg)
        args.update(self._body_args(recv_msg.Message))
        return args


def _mail_message(notifier, recv_msg):
    if not notifier:
        return None
    if getattr(notifier, '_create_mail_message', None):
        return notifier._create_mail_message(recv_msg)
    return None


def _default_sender():
    policy = component.getUtility(ISitePolicyUserEventListener)
    return getattr(policy, 'DEFAULT_EMAIL_SENDER', None)


class MailMessageCorrespondenceLogInfo(object):

    mail_msg = None

    def __init__(self, mail_msg):
        self.mail_msg = mail_msg

    @Lazy
    def Subject(self):
        return self.mail_msg.subject

    @Lazy
    def Body(self):
        body = self.mail_msg.html
        if not body:
            body = self.mail_msg.body
        return body

    @Lazy
    def Recipients(self):
        return tuple(self.mail_msg.send_to)

    @Lazy
    def Sender(self):
        sender = self.mail_msg.sender
        if not sender:
            sender = _default_sender()
        return sender


class NotifierBasedCorrespondenceLogInfo(object):

    package = 'nti.app.messaging'

    recv_msg = None
    notifier = None

    def __init__(self, recv_msg, notifier):
        self.recv_msg = recv_msg
        self.notifier = notifier

    @Lazy
    def Subject(self):
        return self.notifier._subject(self.recv_msg)

    def _render(self, template, ext, data, request):
        body = None
        try:
            template += '.' + ext
            body = render(template, data, request=request)
            if body == data:
                body = None
        except ValueError:
            body = None
        return body

    @Lazy
    def Body(self):
        request = get_current_request()
        data = self.notifier._template_args(self.recv_msg)
        template = self.package + ':' + self.notifier.template
        body = self._render(template, 'pt', data, request)
        if body is None:
            body = self._render(template, 'mak', data, request)
        return body

    @Lazy
    def Recipients(self):
        # We get this implementation if we only have internal notification
        #(not an external email). In that case we want to return no recipients
        return ()

    @Lazy
    def Sender(self):
        sender = self.notifier._email_for(self.recv_msg.Message.From)
        if not sender:
            sender = _default_sender()
        return sender
