""" robotparser2.py

    Copyright (C) 2000  Bastian Kleineidam
    Copyright (C) 2022  Lucy Maber

    You can choose between two licenses when using this package:
    1) GNU GPLv2
    2) PSF license for Python 2.2

    The robots.txt Exclusion Protocol is implemented as specified in
    http://www.robotstxt.org/norobots-rfc.txt
"""

import urllib.parse
import urllib.request
import re
patton_time = r"([0-9][0-9]):([0-9][0-9])[- ]([0-9][0-9]):([0-9][0-9])"

patton_robot_version_3 = r"([0-9]*)\.([0-9]*)\.([0-9]*)"
patton_robot_version_2 = r"([0-9]*)\.([0-9]*)"

patton_time = r"([0-9][0-9]):([0-9][0-9])[- ]([0-9][0-9]):([0-9][0-9])"
patton_request_rate = r"([0-9]*)/([0-9]*)([wdhms])?"
patton_request_rate_time = r"([0-9]*)/([0-9]*)([wdhms])? ([0-9][0-9]):([0-9][0-9])[ -]([0-9][0-9]):([0-9][0-9])"

__all__ = ["RobotFileParser"]

# RequestRate = collections.namedtuple("RequestRate", "requests seconds")


def time_decode(hours, minits, seconds=0):
    return (hours*60*60)+(minits*60)+seconds


def checkTime_range(time_now, end, start):
    return (time_now <= end) and (time_now >= start)


class RobotFileParser2:
    """ This class provides a set of methods to read, parse and answer
    questions about a single robots.txt file.

    """

    def __init__(self, url=''):
        self._regex = False
        self.entries = []
        self.sitemaps = []
        self.indexpage = []
        self.req_rates = []
        self.clean_param = []
        self.default_entry = None
        self.disallow_all = False
        self.allow_all = False
        self.set_url(url)
        self.last_checked = 0

    def mtime(self):
        """Returns the time the robots.txt file was last fetched.

        This is useful for long-running web spiders that need to
        check for new robots.txt files periodically.

        """
        return self.last_checked

    def modified(self):
        """Sets the time the robots.txt file was last fetched to the
        current time.

        """
        import time
        self.last_checked = time.time()

    def set_url(self, url):
        """Sets the URL referring to a robots.txt file."""
        self.url = url
        self.host, self.path = urllib.parse.urlparse(url)[1:3]

    def read(self):
        """Reads the robots.txt URL and feeds it to the parser."""
        try:
            f = urllib.request.urlopen(self.url)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                self.disallow_all = True
            elif err.code >= 400 and err.code < 500:
                self.allow_all = True
        else:
            raw = f.read()
            self.parse(raw.decode("utf-8").splitlines())

    def _add_entry(self, entry):
        if "*" in entry.useragents:
            # the default entry is considered last
            if self.default_entry is None:
                # the first default entry wins
                self.default_entry = entry
        else:
            self.entries.append(entry)

    def parse(self, lines):
        """Parse the input lines from a robots.txt file.

        We allow that a user-agent: line is not preceded by
        one or more blank lines.
        """
        # states:
        #   0: start state
        #   1: saw user-agent line
        #   2: saw an allow or disallow line
        state = 0
        entry = Entry()

        self.modified()
        for line in lines:
            if not line:
                if state == 1:
                    entry = Entry()
                    state = 0
                elif state == 2:
                    self._add_entry(entry)
                    entry = Entry()
                    state = 0
            # remove optional comment and strip line
            i = line.find('#')
            if i >= 0:
                line = line[:i]
            line = line.strip()
            if not line:
                continue
            line = line.split(':', 1)
            if len(line) == 2:
                line[0] = line[0].strip().lower()
                line[1] = urllib.parse.unquote(line[1].strip())

                if line[0] == "user-agent":
                    if state == 2:
                        self._add_entry(entry)
                        entry = Entry()
                    entry.useragents.append(line[1])
                    state = 1

                elif line[0] == "disallow":
                    if state != 0:
                        entry.rulelines.append(RuleLine(line[1], False))
                        state = 2

                elif line[0] == "allow":
                    if state != 0:
                        entry.rulelines.append(RuleLine(line[1], True))
                        state = 2

                elif line[0] == "noindex":
                    if state != 0:
                        entry.rulelines.append(
                            RuleLine(line[1], False, index=True))
                        state = 2

                elif line[0] == "robot-version":
                    if re.match(patton_robot_version_3, line[1]):
                        numbers = re.search(patton_robot_version_3, line[1])
                        major = int(numbers[0])
                        minor = int(numbers[1])
                        patch = int(numbers[2])
                        if major == 2:
                            if minor == 0 and patch == 0:
                                pass
                            else:
                                pass

                        pass
                    if re.match(patton_robot_version_2, line[1]):
                        numbers = re.search(patton_robot_version_2, line[1])
                        major = int(numbers[0])
                        minor = int(numbers[1])
                        if major == 2:
                            if minor == 0:
                                pass
                        pass
                elif line[0] == "crawl-delay":
                    if state != 0:
                        # before trying to convert to int we need to make
                        # sure that robots.txt has valid syntax otherwise
                        # it will crash
                        if line[1].strip().isdigit():
                            entry.delay = int(line[1])
                        state = 2

                elif line[0] == "clean-param":
                    param = line[1].split(' ')
                    entry.clean_param.append((param[0], param[1]))

                elif line[0] == "visit-time":
                    numbers = re.search(patton_time, line[1])
                    entry.visit_times.append(
                        (numbers[0], numbers[1], numbers[2], numbers[3]))

                elif line[0] == "indexpage":
                    self.indexpage.append(line[1])
                elif line[0] == "request-rate":
                    if state != 0:
                        if re.match(patton_request_rate, line[1]):
                            numbers = re.search(patton_request_rate, line[1])
                            metrics = numbers[3]
                            entry.req_rate_default = RequestRate(
                                int(numbers[1]), int(numbers[2]), metrics)
                            state = 2
                        if re.match(patton_request_rate_time, line[1]):
                            p = re.search(patton_request_rate_time, line[1])
                            end = time_decode(int(p[4]), int(p[5]))
                            start = time_decode(int(p[6]), int(p[7]))
                            doc = int(p[1])
                            time = int(p[2])
                            metrics = p[3]
                            entry.req_rates.append(RequestRateTime(
                                doc, time, metrics, start, end))
                            state = 2
                elif line[0] == "sitemap":
                    # According to http://www.sitemaps.org/protocol.html
                    # "This directive is independent of the user-agent line,
                    #  so it doesn't matter where you place it in your file."
                    # Therefore we do not change the state of the parser.
                    self.sitemaps.append(line[1])

        if state == 2:
            self._add_entry(entry)

    def can_fetch(self, useragent, url):
        """using the parsed robots.txt decide if useragent can fetch url"""
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        # Until the robots.txt file has been read or found not
        # to exist, we must assume that no url is allowable.
        # This prevents false positives when a user erroneously
        # calls can_fetch() before calling read().
        if not self.last_checked:
            return False
        # search for given user agent matches
        # the first match counts
        parsed_url = urllib.parse.urlparse(urllib.parse.unquote(url))
        url = urllib.parse.urlunparse(('', '', parsed_url.path,
                                       parsed_url.params, parsed_url.query, parsed_url.fragment))
        url = urllib.parse.quote(url)
        if not url:
            url = "/"
        for entry in self.entries:
            if entry.applies_to(useragent):
                return entry.allowance(url, self._regex)
        # try the default entry last
        if self.default_entry:
            return self.default_entry.allowance(url, self._regex)
        # agent not found ==> access granted
        return True

    def check_visit_time(self, useragent, time):
        output = True
        if not self.mtime():
            return None
        for entry in self.entries:
            output = False
            if entry.applies_to(useragent):
                for visit_time in entry.visit_times:
                    return checkTime_range(time, visit_time)
        if self.default_entry.visit_times:
            return checkTime_range(time, self.default_entry.visit_times)
        return output

    def url_cleanup(self, useragent, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        dict_query = urllib.parse.parse_qs(parsed_url.query)
        if not self.mtime():
            return None
        for entry in self.entries:
            if entry.applies_to(useragent):
                for clean_param in entry.clean_param:
                    if (path in clean_param[1]) and (clean_param[0] in dict_query.keys()):
                        del dict_query[clean_param[0]]
        if self.default_entry:
            for clean_param in self.default_entry.clean_param:
                if (path in clean_param[1]) and (clean_param[0] in dict_query.keys()):
                    del dict_query[clean_param[0]]
        query = urllib.parse.urlencode(dict_query)
        parsed_url = parsed_url._replace(query=query)
        return parsed_url.geturl()

    def crawl_delay(self, useragent):
        if not self.mtime():
            return None
        for entry in self.entries:
            if entry.applies_to(useragent):
                return entry.delay
        if self.default_entry:
            return self.default_entry.delay
        return None

    def request_rate(self, useragent, time):
        if not self.mtime():
            return None
        for entry in self.entries:
            # look in all entry
            if entry.applies_to(useragent):
                for req_rate in entry.req_rates:
                    if req_rate.check(time):
                        return req_rate.get_value()
                return entry.req_rate
        #
        for req_rate in self.default_entry.req_rates:
            if req_rate.check(time):
                return req_rate.get_value()
        #
        if self.default_entry.req_rate_default:
            return self.default_entry.req_rate_default
        return None

    def site_maps(self):
        if not self.sitemaps:
            return None
        return self.sitemaps

    def index_page(self):
        if not self.indexpage:
            return None
        return self.indexpage

    def __str__(self):
        entries = self.entries
        if self.default_entry is not None:
            entries = entries + [self.default_entry]
        return '\n\n'.join(map(str, entries))


class RuleLine:
    """A rule line is a single "Allow:" (allowance==True) or "Disallow:"
       (allowance==False) followed by a path."""

    def __init__(self, path, allowance, index=True):
        if path == '' and not allowance:
            # an empty value means allow all
            allowance = True
        path = urllib.parse.urlunparse(urllib.parse.urlparse(path))
        self.path = urllib.parse.quote(path)
        self.allowance = allowance
        self.index = index

    def applies_to(self, filename, can_regx=False):
        if not can_regx:
            return self.path == "*" or filename.startswith(self.path)
        elif self.path == "*":
            return True
        elif filename.startswith(self.path):
            return True
        else:
            pattern = re.compile(self.path)
            return bool(re.match(pattern, filename))

    def __str__(self):
        return ("Allow" if self.allowance else "Disallow") + ": " + self.path


class RequestRateTime:
    def __init__(self, requests, time, metrics,  start, end):
        self.requests = requests
        self.time = time
        self.start = start
        self.end = end
        if metrics is not None:
            self.metrics = metrics
        else:
            self.metrics = "s"

    def check(self, time):
        return checkTime_range(time, self.start, self.end)

    def get_value(self):
        if self.metrics == "w":
            return (self.requests, self.time*60*60*24*7)
        if self.metrics == "d":
            return (self.requests, self.time*60*60*24)
        if self.metrics == "h":
            return (self.requests, self.time*60*60)
        if self.metrics == "m":
            return (self.requests, self.time*60)
        if self.metrics == "s":
            return (self.requests, self.time)
        return (self.requests, self.time)


class RequestRate:
    def __init__(self, doc, time, metrics):
        self.doc = doc
        self.time = time
        if metrics is not None:
            self.metrics = metrics
        elif metrics is not None:
            self.metrics = "s"

    def get_value(self):
        if self.metrics == "w":
            return (self.doc, self.time*60*60*24*7)
        if self.metrics == "d":
            return (self.doc, self.time*60*60*24)
        if self.metrics == "h":
            return (self.doc, self.time*60*60)
        if self.metrics == "m":
            return (self.doc, self.time*60)
        if self.metrics == "s":
            return (self.doc, self.time)
        return (self.doc, self.time)


class Entry:
    """An entry has one or more user-agents and zero or more rulelines"""

    def __init__(self):
        self.useragents = []
        self.rulelines = []
        self.clean_param = []
        self.req_rates = []
        self.visit_times = []
        self.delay = None
        self.req_rate_default = None

    def __str__(self):
        ret = []
        for agent in self.useragents:
            ret.append(f"User-agent: {agent}")
        if self.delay is not None:
            ret.append(f"Crawl-delay: {self.delay}")
        if self.req_rate_default is not None:
            rate = self.req_rate_default
            ret.append(
                f"Request-rate: {rate.doc}/{rate.time}{rate.metrics}")
        ret.extend(map(str, self.rulelines))
        return '\n'.join(ret)

    def applies_to(self, useragent):
        """check if this entry applies to the specified agent"""
        # split the name token and make it lower case
        useragent = useragent.split("/")[0].lower()
        for agent in self.useragents:
            if agent == '*':
                # we have the catch-all agent
                return True
            agent = agent.lower()
            if agent in useragent:
                return True
        return False

    def allowance(self, filename, can_regx=False):
        """Preconditions:
        - our agent applies to this entry
        - filename is URL decoded"""
        for line in self.rulelines:
            if line.applies_to(filename, can_regx=can_regx):
                return line.allowance
        return True
