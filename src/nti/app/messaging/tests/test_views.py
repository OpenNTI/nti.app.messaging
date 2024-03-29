#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import same_instance
from hamcrest import has_properties
does_not = is_not

from zope import component

from zope.security.interfaces import IPrincipal

from nti.app.messaging.utils import get_user

from nti.messaging.interfaces import IMailbox

from nti.messaging.model import PeerToPeerMessage

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestMessagingViews(ApplicationLayerTest):

    def _link_with_rel(self, links, rel):
        for link in links:
            if link['rel'] == rel:
                return link
        return None

    def _get_sent_messages(self, username):
        user = get_user(username)
        mailbox = IMailbox(user)
        return list(mailbox.Sent.values())

    def _get_received_messages(self, username):
        user = get_user(username)
        mailbox = IMailbox(user)
        return list(mailbox.Received.values())

    def _new_messsage(self, sender, receiver,
                      subject="Bleach", body="Bankai"):
        if not isinstance(receiver, (tuple, list)):
            receiver = [receiver]
        sender = get_user(sender)
        To = [IPrincipal(x) for x in receiver]
        message = PeerToPeerMessage(To=To,
                                    body=body,
                                    Subject=subject,
                                    From=IPrincipal(sender))
        mailbox = component.getMultiAdapter((sender, message),
                                            IMailbox)
        mailbox.send(message)
        return message

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_get_mailbox(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')
            ichigo, aizen = 'ichigo', 'aizen'

        # users with a mailbox have the link to get it
        href = '/dataserver2/users/ichigo'
        resp = self.testapp.get(href, status=200,
                                extra_environ=self._make_extra_environ(username=ichigo))
        resp = resp.json_body
        assert_that(resp,
                    has_entry('Links',
                              has_item(has_entry('rel', 'mailbox'))))

        # fetching the link works for the owner
        href = self._link_with_rel(resp['Links'], 'mailbox')['href']
        resp = self.testapp.get(href, status=200,
                                extra_environ=self._make_extra_environ(username=ichigo))
        resp = resp.json_body
        assert_that(resp,
                    has_entry('MimeType', 'application/vnd.nextthought.messaging.mailbox'))

        # but you can't fetch someone elses
        self.testapp.get(href, status=403,
                         extra_environ=self._make_extra_environ(username=aizen))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_new_message(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')

        ext_obj = {
            "Subject": "How are you",
            "From": "ichigo",
            "To": ["aizen"],
            "body": "how are you",
            "MimeType": "application/vnd.nextthought.messaging.peertopeermessage"
        }

        # can't post new messgon on someone else's IMailbox
        href = '/dataserver2/users/ichigo/mailbox'
        self.testapp.post_json(href, ext_obj,
                               status=403,
                               extra_environ=self._make_extra_environ(username='aizen'))

        # post new message on the creator's IMailbox
        res = self.testapp.post_json(href, ext_obj,
                                     status=201,
                                     extra_environ=self._make_extra_environ(username="ichigo"))

        assert_that(res.json_body,
                    has_entry('Links',
                              has_item(has_entry('rel', 'reply'))))

        assert_that(res.json_body,
                    has_entries(u'MimeType', u'application/vnd.nextthought.messaging.conversation',
                                u'MostRecentMessage', is_not(none()),
                                u'UnOpenedCount', 1,
                                u'Participants', [u'aizen', u'ichigo']))

        # verify the message is in the sender's IMailbox and the
        # receiver's IMailbox
        with mock_dataserver.mock_db_trans(self.ds):
            sent_messages = self._get_sent_messages('ichigo')
            assert_that(sent_messages, has_length(1))
            assert_that(sent_messages[0],
                        has_properties({'Subject': 'How are you',
                                        'From': IPrincipal('ichigo'),
                                        'To': (IPrincipal('aizen'),),
                                        'body': 'how are you'}))

            received_messages = self._get_received_messages('aizen')
            assert_that(received_messages, has_length(1))
            assert_that(received_messages[0].Message,
                        same_instance(sent_messages[0]))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_reply_message(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')
            self._create_user('rukia')

        # creating a root IMessage
        with mock_dataserver.mock_db_trans(self.ds):
            message_id = self._new_messsage("ichigo", "aizen").id

        # reply to the root IMessage
        reply_url = "/dataserver2/users/%s/mailbox/Sent/%s/@@reply" % (
            "ichigo", message_id)

        ext_obj = {
            "Subject": "second",
            "From": "aizen",
            "To": ["ichigo"],
            "body": "how are you",
            "MimeType": "application/vnd.nextthought.messaging.peertopeermessage"
        }

        # others except for the creator and receivers can't reply on the
        # message.
        self.testapp.post_json(reply_url,
                               ext_obj,
                               status=401,
                               extra_environ=self._make_extra_environ(username=None))
        self.testapp.post_json(reply_url,
                               ext_obj,
                               status=403,
                               extra_environ=self._make_extra_environ(username="rukia"))

        result = self.testapp.post_json(reply_url,
                                        ext_obj,
                                        status=201,
                                        extra_environ=self._make_extra_environ(username="aizen"))
        assert_that(result.json_body['Subject'], is_('second'))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_mark_opened(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')

        with mock_dataserver.mock_db_trans(self.ds):
            self._new_messsage("ichigo", "aizen")

            received_messages = self._get_received_messages('aizen')
            assert_that(received_messages, has_length(1))
            assert_that(received_messages[0].ViewDate, is_(none()))
            mid = received_messages[0].Message.id
        href = "/dataserver2/users/%s/mailbox/Received/%s/@@opened" % (
            "aizen", mid)

        # can't viewed the others' HousingReceivedMessages
        self.testapp.post_json(href, {},
                               status=401,
                               extra_environ=self._make_extra_environ(username=None))

        self.testapp.post_json(href, {},
                               status=403,
                               extra_environ=self._make_extra_environ(username="ichigo"))

        self.testapp.post_json(href, {},
                               status=200,
                               extra_environ=self._make_extra_environ(username="aizen"))

        with mock_dataserver.mock_db_trans(self.ds):
            received_messages = self._get_received_messages('aizen')
            assert_that(received_messages, has_length(1))
            assert_that(received_messages[0].ViewDate, is_not(none()))

        # has been viewed.
        self.testapp.post_json(href, {},
                               status=422,
                               extra_environ=self._make_extra_environ(username="aizen"))

    def _reply(self, reply_url, from_username, to_username, subject="second"):
        ext_obj = {
            "Subject": subject,
            "From": from_username,
            "To": [to_username] if not isinstance(to_username, list) else to_username,
            "body": "how are you",
            "MimeType": "application/vnd.nextthought.messaging.peertopeermessage"
        }
        self.testapp.post_json(reply_url,
                               ext_obj,
                               status=201,
                               extra_environ=self._make_extra_environ(username=from_username))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_thread(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')
            self._create_user('rukia')

        # create a rooting Message
        with mock_dataserver.mock_db_trans(self.ds):
            message = self._new_messsage("ichigo", ["aizen"], subject="first")
            mid = message.id

        href = "/dataserver2/users/%s/mailbox/Sent/%s/@@reply" % ("ichigo", mid)
        self._reply(href, "aizen", ["ichigo"], subject="second")
        self._reply(href, "ichigo", ["aizen"], subject="third")
        self._reply(href, "aizen", ["ichigo"], subject="fourth")
        self._reply(href, "aizen", ["ichigo"], subject="fifth")

        href = "/dataserver2/users/%s/mailbox/Sent/%s/@@thread" % ("ichigo", mid)
        result = self.testapp.get(href,
                                  status=200,
                                  extra_environ=self._make_extra_environ(username="ichigo"))
        assert_that(result.json_body['Total'], is_(5))
        subjects = [x['Subject'] for x in result.json_body['Items']]
        assert_that(subjects,
                    has_items(u'first',
                              u'second',
                              u'third',
                              u'fourth',
                              u'fifth'))

        result = self.testapp.get(href,
                                  status=200,
                                  extra_environ=self._make_extra_environ(username="aizen"))
        assert_that(result.json_body['Total'], is_(5))
        subjects = [x['Subject'] for x in result.json_body['Items']]
        assert_that(subjects,
                    has_items(u'first',
                              u'second',
                              u'third',
                              u'fourth',
                              u'fifth'))

        self.testapp.get(href,
                         status=401,
                         extra_environ=self._make_extra_environ(username=None))
        self.testapp.get(href,
                         status=403,
                         extra_environ=self._make_extra_environ(username="rukia"))
        
    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_conversations(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')
            self._create_user('aizen')
            self._create_user('rukia')
            self._create_user('kenpachi')

        with mock_dataserver.mock_db_trans(self.ds):
            message = self._new_messsage("ichigo", ["aizen"], subject="first12")
            mid = message.id

            # rukia only has sent messages
            self._new_messsage("rukia", ["ichigo"], subject="first31")
            self._new_messsage("rukia", ["aizen"], subject="first32")

            # kenpachi only has received messages.
            self._new_messsage("ichigo", ["kenpachi"], subject="first14")
            self._new_messsage("aizen", ["kenpachi"], subject="first24")
            self._new_messsage("rukia", ["kenpachi"], subject="first34")

        href = "/dataserver2/users/%s/mailbox/Sent/%s/@@reply" % ("ichigo", mid)
        self._reply(href, "aizen", ["ichigo"], subject="second12")
        self._reply(href, "ichigo", ["aizen"], subject="third12")
        self._reply(href, "ichigo", ["aizen"], subject="fourth12")

        href = "/dataserver2/users/%s/mailbox/@@conversations" % "ichigo"
        result = self.testapp.get(href, 
                                  status=200, 
                                  extra_environ=self._make_extra_environ(username="ichigo"))
        assert_that(result.json_body['Items'], has_length(3))

        href = "/dataserver2/users/%s/mailbox/@@conversations" % "aizen"
        result = self.testapp.get(href, 
                                  status=200, 
                                  extra_environ=self._make_extra_environ(username="aizen"))
        assert_that(result.json_body['Items'], has_length(3))

        href = "/dataserver2/users/%s/mailbox/@@conversations" % "rukia"
        result = self.testapp.get(href, 
                                  status=200, 
                                  extra_environ=self._make_extra_environ(username="rukia"))
        assert_that(result.json_body['Items'], has_length(3))

        href = "/dataserver2/users/%s/mailbox/@@conversations" % "kenpachi"
        result = self.testapp.get(href, 
                                  status=200, 
                                  extra_environ=self._make_extra_environ(username="kenpachi"))
        assert_that(result.json_body['Items'], has_length(3))
