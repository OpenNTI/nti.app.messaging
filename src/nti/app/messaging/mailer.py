#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mailers that somehow filter their arguments before
actually creating or queuing mail.

.. $Id: filtered_template_mailer.py 96206 2016-09-03 18:12:38Z chris.utz $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


from nti.mailer.filtered_template_mailer import NextThoughtOnlyMailer


class TestMailer(NextThoughtOnlyMailer):
    """
    This mailer ensures we only send email to a whitelisted list
    of domains or emails addresses.  Unlike it's superclass it actually
    filters mail sent via the queue_simple_html_text_email.
    """

    allowed_domains = ('nextthought.com', )
    allowed_emails = ()

    def _transform_recipient(self, addr):
        """
        We don't do any transforming, only filtering
        """
        return addr

    def _should_send_to_addr(self, addr):
        if addr and addr.lower() in self.allowed_emails:
            return True
        domain = addr.rsplit('@', 1)[-1]
        return domain in self.allowed_domains

    def queue_simple_html_text_email(self, *args, **kwargs):
        """
        Creates a message an enques it for sending
        """
        msg = self.create_simple_html_text_email(*args, **kwargs)
        if not msg:
            # create_simple_html_text_email return None for no recipients
            return None

        # if we have not recipients (this may filter them) don't send
        # a message. Just log
        recipients = msg.recipients
        final_recipient_count = len(recipients)
        original_recipient_count = len(kwargs.get('recipients', ()))

        if original_recipient_count != final_recipient_count:
            logger.debug('Filtered %s of %s recipients. Sending to (%s)',
                         original_recipient_count - final_recipient_count, 
                         original_recipient_count, recipients)

        if not recipients:
            # no recipients, we just noop
            return

        return self._send_pyramid_mailer_mail(msg, 
                                              recipients=recipients, 
                                              request=kwargs.get('request'))
