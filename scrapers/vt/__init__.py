from utils import url_xpath
from openstates.scrape import State
from .bills import VTBillScraper
from .events import VTEventScraper


# As of March 2018, Vermont appears to be throttling hits
# to its website. After a week of production failures, we
# tried rate-limiting our requests, and the errors went away
# (Reminder: default is 60 RPM)
# This limit might also be possible to remove once we switch to
# the official API for bills:
# https://github.com/openstates/openstates/issues/2196
settings = dict(SCRAPELIB_RPM=20)


class Vermont(State):
    scrapers = {
        "bills": VTBillScraper,
        "events": VTEventScraper,
    }
    legislative_sessions = [
        {
            "_scraped_name": "2009-2010 Session",
            "classification": "primary",
            "identifier": "2009-2010",
            "name": "2009-2010 Regular Session",
            "start_date": "2009-01-07",
            "end_date": "2010-05-12",
        },
        {
            "_scraped_name": "2011-2012 Session",
            "classification": "primary",
            "identifier": "2011-2012",
            "name": "2011-2012 Regular Session",
            "start_date": "2011-01-05",
            "end_date": "2012-05-05",
        },
        {
            "_scraped_name": "2013-2014 Session",
            "classification": "primary",
            "identifier": "2013-2014",
            "name": "2013-2014 Regular Session",
            "start_date": "2013-01-09",
            "end_date": "2014-05-10",
        },
        {
            "_scraped_name": "2015-2016 Session",
            "classification": "primary",
            "identifier": "2015-2016",
            "name": "2015-2016 Regular Session",
            "start_date": "2015-01-07",
            "end_date": "2016-05-06",
        },
        {
            "_scraped_name": "2017-2018 Session",
            "classification": "primary",
            "identifier": "2017-2018",
            "name": "2017-2018 Regular Session",
            "start_date": "2017-01-04",
            "end_date": "2018-05-12",
        },
        {
            "_scraped_name": "2018 Special Session",
            "classification": "special",
            "identifier": "2018ss1",
            "name": "2018 Special Session",
            "start_date": "2018-05-23",
            "end_date": "2018-06-29",
        },
        {
            "_scraped_name": "2019-2020 Session",
            "classification": "primary",
            "identifier": "2019-2020",
            "name": "2019-2020 Regular Session",
            "start_date": "2019-01-09",
            "end_date": "2020-09-25",
        },
        {
            "_scraped_name": "2021-2022 Session",
            "classification": "primary",
            "identifier": "2021-2022",
            "name": "2021-2022 Regular Session",
            "start_date": "2021-01-06",
            "end_date": "2021-05-12",
            "active": False,
        },
        {
            "_scraped_name": "2021 Special Session",
            "classification": "special",
            "identifier": "2021S1",
            "name": "2021 Special Session",
            "start_date": "2021-11-22",
            "end_date": "2021-11-22",
            "active": False,
        },
        {
            "_scraped_name": "2023-2024 Session",
            "classification": "primary",
            "identifier": "2023-2024",
            "name": "2023-2024 Regular Session",
            "start_date": "2023-01-04",
            "end_date": "2025-05-09",
            "active": False,
        },
        {
            "_scraped_name": "2025-2026 Session",
            "classification": "primary",
            "identifier": "2025-2026",
            "name": "2025-2026 Regular Session",
            "start_date": "2025-01-08",
            "end_date": "2026-05-08",
            "active": True,
        },
    ]
    ignored_scraped_sessions = [
        "2020 Training Session",
        "2009 Special Session",
    ]

    site_ids = {"2018ss1": "2018.1", "2021S1": "2021.1"}

    # 2021 TODO: is this function still correct?
    def get_year_slug(self, session):
        return self.site_ids.get(session, session[5:])

    def get_session_list(self):
        # verify=False to match every fetch in this scraper's own bills.py,
        # which already passes it at all eight call sites against this same
        # host. legislature.vermont.gov serves ONLY its leaf certificate and
        # omits the GlobalSign RSA OV SSL CA 2018 intermediate, so the chain
        # cannot be built and python raises
        # CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate.
        # Browsers hide this by fetching the issuer over AIA; requests does
        # not. The certificate itself is valid (to 2027-01-10) and the host is
        # reachable, so this is an incomplete chain served by Vermont rather
        # than a site that is down. This one line was the only fetch in the
        # scraper still verifying, and it is why VT sat in SKIP_STATES being
        # described as "unreachable" while the rest of its scraper worked.
        sessions = url_xpath(
            "https://legislature.vermont.gov/bill/search/2016",
            '//fieldset/div[@id="Form_SelectSession_selected_session_Holder"]'
            "/div/select/option/text()",
            verify=False,
        )
        sessions = (session.replace(",", "").strip() for session in sessions)
        return sessions
