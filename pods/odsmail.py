from __future__ import print_function
from __future__ import absolute_import
import smtplib
import getpass

from . import config

gmail_sender= config.config.get('Gmail', 'user')
gmail_name = config.config.get('Gmail', 'name')

class gmail():
    def __init__(self, username=None, name=None):
        """Open an SMTP TLS session for gmail."""
        self.session = smtplib.SMTP('smtp.gmail.com', 587)
        self.session.ehlo()
        self.session.starttls()
        if name is None:
            self.name = gmail_name
        else:
            self.name = name
        if username is None:
            self.username = gmail_sender
        else:
            self.username = username
        self.password = None
        self.get_password()
        self.session.login(self.username,self.password)

    def get_password(self):
        if self.password is None:
            print("Check console for password input!")
            import sys
            sys.stdout.flush()
            self.password = getpass.getpass("Enter your password for gmail:")
        

    def send(self, recipient, subject, body, cc=[], reply_to=None, html=True):
        # The below code never changes, though obviously those
        # variables need values.
        if self.name is not None:
            sender = self.name + '<' + self.username + '>'
        else:
            sender = self.username
        if reply_to is None:
            reply_to = sender
        email_cc = ';'.join(cc)
        from email.mime.text import MIMEText
        if html:
            message = MIMEText(body.encode('utf-8'), 'html', _charset="UTF-8")
        else:
            message = MIMEText(body.encode('utf-8'), 'plain', _charset="UTF-8")

        message['From'] = sender
        message['To'] = recipient
        message['Cc'] = email_cc
        message['Reply-to'] = reply_to
        message['Subject'] = subject
        
        msg_full = message.as_string()


        self.session.sendmail(self.username, recipient, msg_full)
