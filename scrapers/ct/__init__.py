from openstates.scrape import State
from .bills import CTBillScraper
from .events import CTEventScraper
from .votes import CTVoteScraper

settings = {"SCRAPELIB_RPM": 20}

SKIP_SESSIONS = {"incoming", "pub", "CGAAudio", "rba", "NCSL", "FOI_1", "stainedglass"}


class Connecticut(State):
    scrapers = {
        "bills": CTBillScraper,
        "events": CTEventScraper,
        "votes": CTVoteScraper,
    }
    legislative_sessions = [
        {
            "_scraped_name": "2011",
            "identifier": "2011",
            "name": "2011 Regular Session",
            "start_date": "2011-01-05",
            "end_date": "2011-06-08",
        },
        {
            "_scraped_name": "2012",
            "identifier": "2012",
            "name": "2012 Regular Session",
            "start_date": "2012-02-08",
            "end_date": "2012-05-09",
        },
        {
            "_scraped_name": "2013",
            "identifier": "2013",
            "name": "2013 Regular Session",
            "start_date": "2013-01-09",
            "end_date": "2013-06-05",
        },
        {
            "_scraped_name": "2014",
            "identifier": "2014",
            "name": "2014 Regular Session",
            "start_date": "2014-02-05",
            "end_date": "2014-05-07",
        },
        {
            "_scraped_name": "2015",
            "identifier": "2015",
            "name": "2015 Regular Session",
            "start_date": "2015-01-07",
            "end_date": "2015-06-03",
        },
        {
            "_scraped_name": "2016",
            "end_date": "2016-05-04",
            "identifier": "2016",
            "name": "2016 Regular Session",
            "start_date": "2016-02-03",
        },
        {
            "_scraped_name": "2017",
            "identifier": "2017",
            "name": "2017 Regular Session",
            "start_date": "2017-01-04",
            "end_date": "2017-06-07",
        },
        {
            "_scraped_name": "2018",
            "identifier": "2018",
            "name": "2018 Regular Session",
            "start_date": "2018-02-07",
            "end_date": "2018-05-09",
        },
        {
            "_scraped_name": "2019",
            "identifier": "2019",
            "name": "2019 Regular Session",
            "start_date": "2019-01-09",
            "end_date": "2019-06-05",
        },
        {
            "_scraped_name": "2020",
            "identifier": "2020",
            "name": "2020 Regular Session",
            "start_date": "2020-02-05",
            "end_date": "2020-05-06",
        },
        {
            "_scraped_name": "2021",
            "identifier": "2021",
            "name": "2021 Regular Session",
            "start_date": "2021-01-06",
            "end_date": "2021-06-09",
            "active": False,
        },
        {
            "_scraped_name": "2022",
            "identifier": "2022",
            "name": "2022 Regular Session",
            "start_date": "2022-02-09",
            "end_date": "2022-05-04",
            "active": False,
        },
        {
            "_scraped_name": "2023",
            "identifier": "2023",
            "name": "2023 Regular Session",
            "start_date": "2023-01-04",
            "end_date": "2023-05-04",
            "active": False,
        },
        {
            "_scraped_name": "2024",
            "identifier": "2024",
            "name": "2024 Regular Session",
            "start_date": "2024-01-04",
            "end_date": "2024-05-08",
            "active": False,
        },
        {
            "_scraped_name": "2025",
            "identifier": "2025",
            "name": "2025 Regular Session",
            "start_date": "2025-01-08",
            "end_date": "2025-06-04",
            "active": False,
        },
        {
            "_scraped_name": "2026",
            "identifier": "2026",
            "name": "2026 Regular Session",
            "start_date": "2026-02-04",
            "end_date": "2026-05-06",
            "active": True,
        },
    ]
    ignored_scraped_sessions = [
        "1991",
        "1992",
        "1993",
        "1994",
        "1995",
        "1996",
        "1997",
        "1998",
        "1999",
        "2000",
        "2001",
        "2002",
        "2003",
        "2004",
        "2005",
        "2006",
        "2007",
        "2008",
        "2009",
        "2010",
    ]

    def get_session_list(self):
        from utils.lxmlize import url_xpath

        # search.cga.state.ct.us served IIS 503 from 14 Nov 2026 on; the bill
        # status page on www.cga.ct.gov carries the same which_year menu
        # (LawSignals ETL-28)
        urls = [
            "https://search.cga.state.ct.us/r/basic/Fbuttons.asp",
            "https://www.cga.ct.gov/asp/cgabillstatus/cgabillstatus.asp",
        ]
        for i, url in enumerate(urls):
            try:
                # www.cga.ct.gov sends an incomplete chain (verify fails)
                years = url_xpath(
                    url, "//select[@name='which_year']/option/text()", verify=False
                )
            except Exception:
                if i == len(urls) - 1:
                    raise
                continue
            years = set(x.strip() for x in years if x.strip())
            if years:
                return years
        raise ValueError("no which_year options on any CT session list page")
