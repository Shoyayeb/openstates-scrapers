import requests
import lxml.html
import logging
import os
import time


# Sent when a caller does not name its own. requests otherwise announces
# `python-requests/x.y`, and some legislature sites sit behind a WAF that
# rejects that outright: Utah's returns an F5 "Request Rejected" page as
# **HTTP 200** with a 246-byte body, so nothing raises, the xpath below simply
# matches nothing, get_session_list() returns [] and check_session_list aborts
# the whole state before a single bill is scraped. Measured on
# le.utah.gov/bills/billSearch.jsp: 0/6 populated with no User-Agent, 6/6 with
# this one. 32 states call url_xpath from get_session_list() and only three
# named a user_agent, so the default is where this belongs. PA and OH already
# pass their own and are unaffected.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def url_xpath(url, path, verify=None, user_agent=None, timeout=60, retries=3):
    headers = {"user-agent": user_agent or DEFAULT_USER_AGENT}

    if verify is None:
        verify = os.getenv("VERIFY_CERTS", "True").lower() == "true"

    # url_xpath is used by many states' get_session_list(), which runs before
    # scraping. A bare requests.get with no timeout and no retry meant a single
    # transient network blip (RemoteDisconnected, ConnectTimeout, connection
    # reset) aborted the entire state run. Add a timeout and retry transient
    # errors a few times with short backoff before giving up.
    last_exc = None
    res = None
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, verify=verify, headers=headers, timeout=timeout)
            break
        except requests.exceptions.RequestException as e:
            last_exc = e
            logging.warning(
                f"url_xpath {url} attempt {attempt}/{retries} failed: {e}"
            )
            if attempt < retries:
                time.sleep(2 * attempt)
    if res is None:
        raise last_exc

    try:
        doc = lxml.html.fromstring(res.text)
    except Exception:
        logging.error(
            f"Failed to retrieve xpath from {url} :: returned:\n"
            f"CONTENT: {res.content} \n"
            f"RETURN CODE: {res.status_code}"
        )
        raise
    result = doc.xpath(path)
    # An empty match is how a WAF block looks from here: HTTP 200, no
    # exception, nothing to retry, and a caller that returns [] and aborts a
    # whole state. Say so, so the next one is visible rather than silent.
    if not result:
        logging.warning(
            f"url_xpath {url} returned 200 but matched nothing for {path!r} "
            f"(body {len(res.content)} bytes). If the body is tiny this is "
            f"likely a WAF rejection served as 200."
        )
    return result


class LXMLMixin(object):
    """Mixin for adding LXML helper functions to Open States code."""

    def lxmlize(self, url, raise_exceptions=False, verify=None):
        """Parses document into an LXML object and makes links absolute.

        Args:
            url (str): URL of the document to parse.
        Returns:
            Element: Document node representing the page.
        """
        if verify is None:
            verify = os.getenv("VERIFY_CERTS", "True").lower() == "true"

        try:
            # This class is always mixed into subclasses of `Scraper`,
            # which have a `get` method defined.
            response = self.get(url, verify=verify)
        except requests.exceptions.SSLError:
            self.warning(
                "`self.lxmlize()` failed due to SSL error, trying "
                "an unverified `self.get()` (i.e. `requests.get()`)"
            )
            response = self.get(url, verify=False)

        if raise_exceptions:
            response.raise_for_status()

        page = lxml.html.fromstring(response.text)
        page.make_links_absolute(url)

        return page

    def get_node(self, base_node, xpath_query):
        """Searches for node in an element tree.

        Attempts to return only the first node found for an xpath query. Meant
        to cut down on exception handling boilerplate.

        Args:
            base_node (Element): Document node to begin querying from.
            xpath_query (str): XPath query to define nodes to search for.
        Returns:
            Element: First node found that matches the query.
        """
        try:
            node = base_node.xpath(xpath_query)[0]
        except IndexError:
            node = None

        return node

    def get_nodes(self, base_node, xpath_query):
        """Searches for nodes in an element tree.

        Attempts to return all nodes found for an xpath query. Meant to cut
        down on exception handling boilerplate.

        Args:
            base_node (Element): Document node to begin querying from.
            xpath_query (str): Xpath query to define nodes to search for.
        Returns:
            List[Element]: All nodes found that match the query.
        """
        return base_node.xpath(xpath_query)
