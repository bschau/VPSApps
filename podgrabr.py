""" podgrabr

Requirements: feedparser, request
"""
# pylint: disable=too-few-public-methods
# pylint: disable=locally-disabled
# pylint: disable=duplicate-code
# pylint: disable=bare-except
# pylint: disable=too-many-instance-attributes
import dbm
import os
import json
import platform
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
import requests


USER_AGENT = "blogtrottr/2.0"


class PodGrabr():
    """ PodGrabr backbone. """

    def __init__(self):
        """ Constructor. """
        self.settings = self.load_settings()
        self.html = ""


    @staticmethod
    def load_settings():
        """ Load default settings. """
        home = os.path.expanduser('~')
        full_path = os.path.join(home, '.vpsappsrc')
        with open(full_path, encoding='utf-8') as json_file:
            return json.load(json_file)


    def execute(self):
        """ Run the handler. """
        cache = self.get_cache_file()
        feeds = self.get_feeds()

        seen = {}
        for feed in feeds:
            self.load_feed(cache, seen, feed)

        self.persist_seen(cache, seen)
        cache.close()


    @staticmethod
    def get_cache_file():
        """ Get the cache file. """
        file = '_podgrabrT' if platform.system() == 'Windows' else '.podgrabrT'

        home = os.path.expanduser('~')
        full_path = os.path.join(home, file)
        return dbm.open(full_path, 'c')


    @staticmethod
    def get_feeds():
        """ Get the feeds file. """
        file = '_podgrabr' if platform.system() == 'Windows' else '.podgrabr'

        home = os.path.expanduser('~')
        full_path = os.path.join(home, file)
        with open(full_path, encoding='utf-8') as json_file:
            return json.load(json_file)


    @staticmethod
    def can_cope_with_bozo(bozo_exception):
        """ Can we copy with the bozo exception?
            Args:
                bozo_exception: exception
        """
        bozo_exception = bozo_exception.lower()
        if 'document declared as' in bozo_exception:
            return True

        if 'is not an xml media type' in bozo_exception:
            return True

        if 'no content-type specified' in bozo_exception:
            return True

        return False


    def load_feed(self, cache, seen, feed):
        """ Main method.
            Args:
                self: self
                cache: cache db
                seen: the empty seen array
                feed: feed
        """
        self.html = ""
        headers = {'User-Agent': USER_AGENT, 'Connection': 'close'}
        try:
            data = requests.get(feed["RssUrl"],
                                headers=headers,
                                timeout=30).content.strip()
        except requests.exceptions.Timeout:
            self.html = self.html + '<h1><a href="' + feed["WebUrl"]
            self.html = self.html + '">' + feed["Name"] + "</a></h1>"
            self.html = self.html + '<p style="color: red">'
            self.html = self.html + 'Timeout - waited 30 seconds</p>'
            return
        except requests.exceptions.RequestException as req_exc:
            self.html = self.html + '<h1><a href="' + feed["WebUrl"]
            self.html = self.html + '">' + feed["Name"] + "</a></h1>"
            self.html = self.html + '<p style="color: red">'
            self.html = self.html + str(req_exc) + '</p>'
            return

        rss = feedparser.parse(data)
        if rss.bozo > 0:
            exception = str(rss.bozo_exception)
            if not self.can_cope_with_bozo(exception):
                self.html = self.html + '<h1><a href="' + feed["WebUrl"]
                self.html = self.html + '">' + feed["Name"] + "</a></h1>"
                self.html = self.html + '<p style="color: red">'
                self.html = self.html + exception + '</p>'
                return

        cache_time = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime())
        for item in rss['items']:
            cache_key = feed['CacheKey'] + item['id']
            if cache.get(cache_key, '') == '':
                link = self.get_link(item)
                self.html = ""
                self.html = self.html + '<h1><a href="' + feed["WebUrl"]
                self.html = self.html + '">' + feed["Name"] + ': '
                self.html = self.html + item['title'] + "</a></h1>"
                self.html = self.html + '<p>Offentliggjort: ' + item['published'] + '</p>'
                if link is None:
                    self.html = self.html + '<p>No audio link!</p>'
                else:
                    self.html = self.html + self.get_description(feed['Htmlize'],
                                                                 item['description'])
                    self.html = self.html + '<p><a href="' + link + '">Download</a></p>'

                seen[cache_key] = cache_time
                title = self.title()
                page = self.page(title, self.html)
                self.deliver(title, page)


    @staticmethod
    def get_description(htmlize, description):
        """ Possibly convert description to HTML.
            Arguments:
                htmlize - should HTMLize description
                description - guess what
        """
        if not htmlize:
            return description

        return "<p>" + description.replace('\n', '<br />') + "</p>"


    @staticmethod
    def get_link(item):
        """ Get audio link.
            Arguments:
                item - item
        """
        for link in item['links']:
            if link['type'] == 'audio/mpeg':
                return link['href']

        return None


    @staticmethod
    def persist_seen(cache, seen):
        """ Add seen link to cache - happens after attempt to send email.
            Arguments:
                cache: cache db
                seen: array with seen links
        """
        for link in seen:
            cache[link] = seen[link]


    @staticmethod
    def title():
        """ Get title of mail. """
        now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        return f"PodGrabr {now}"


    @staticmethod
    def page(title, html):
        """ Get HTML page.
            Arguments:
                title - title
                html - body html
        """
        return f"""<!DOCTYPE html>
<html dir="ltr" lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width" />
    <title>{title}</title>
</head>
<body>
{html}
</body>
</html>"""


    def deliver(self, title, body):
        """ Delivery email by SMTP.
            Arguments:
                title: mail title
                body: body text
        """
        text = "Please read this in a HTML mail user agent."
        recipients = self.settings['podgrabrto']
        message = MIMEMultipart('alternative')
        message['Subject'] = title
        message['From'] = self.settings['from']
        message['To'] = ",".join(recipients)
        plain_text = MIMEText(text, 'plain')
        html_text = MIMEText(body, 'html')
        message.attach(plain_text)
        message.attach(html_text)

        mail = smtplib.SMTP('localhost')
        mail.sendmail(message['From'], recipients, message.as_string())
        mail.quit()


if __name__ == '__main__':
    PodGrabr().execute()
