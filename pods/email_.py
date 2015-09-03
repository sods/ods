import smtplib
import getpass

from config import *

gmail_sender= config.get('Gmail', 'user')
gmail_name = config.get('Gmail', 'name')

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
            print "Check console for password input!"
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
        if html:
            content_type = 'text/html'
        else:
            content_type = 'text/plain'
        headers = "\r\n".join(["from: " + sender,
                               "subject: " + subject,
                               "cc: " + email_cc,
                               "to: " + recipient,
                                "reply-to: " + reply_to,
                               "mime-version: 1.0",
                               "content-type: " + content_type])

        # body_of_email can be plaintext or html!                    
        content = headers + "\r\n\r\n" + body
        self.session.sendmail(self.username, recipient, content)
