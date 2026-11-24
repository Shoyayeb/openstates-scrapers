import datetime
import html.parser
import json
import lxml
import re
import requests

from openstates.exceptions import EmptyScrape
from openstates.scrape import Scraper, Event

# LawSignals ETL-28: from 24 November 2026 Cloudflare in front of legvi.org
# answers python-requests' default User-Agent with a 403 block page on every
# month; the same POST with a browser User-Agent returns the calendar.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


class VIEventScraper(Scraper):
    seen = []

    def scrape(self):

        event_count = 0

        year = datetime.datetime.today().year
        for month in range(1, 13):
            self.info(f"Posting {year}-{month}")
            data = {
                "action": "mec_monthly_view_load_month",
                "mec_year": year,
                "mec_month": str(month).zfill(2),
                "atts[sf_status]": "0",
                "atts[sf_display_label]": "0",
                "atts[show_past_events]": "1",
                "atts[show_only_past_events]": "0",
                "atts[show_only_ongoing_events]": "0",
                "atts[_edit_lock]": "1676605531:1",
                "atts[_edit_last]": "1",
                "atts[ex_category]": "",
                "atts[ex_location]": "",
                "atts[ex_organizer]": "",
                "atts[sf_reset_button]": "0",
                "atts[sf_refine]": "0",
                "atts[show_only_one_occurrence]": "0",
                "atts[show_ongoing_events]": "0",
                "atts[id]": "1376753",
                "atts[sed_method]": "0",
                "atts[image_popup]": "0",
                "apply_sf_date": "0",
                "navigator_click": "true",
            }

            try:
                res = requests.post(
                    "https://legvi.org/wp-admin/admin-ajax.php",
                    data=data,
                    headers=BROWSER_HEADERS,
                    timeout=30,
                )
            except (requests.ConnectionError, requests.Timeout):
                # LawSignals ETL-28: skip the month rather than raise here.
                # EmptyScrape after an event was yielded is itself an error,
                # so a mid-calendar outage ended the whole run. The count
                # below still raises EmptyScrape when every month failed.
                self.warning(f"legvi.org unreachable for {month}/{year}, skipping")
                continue
            # 24 November 2026: legvi.org answered one month with an empty body
            # (JSONDecodeError) and the run ended there. Same treatment.
            try:
                page = json.loads(res.content)
                page = lxml.html.fromstring(page["month"])
            except (ValueError, KeyError, TypeError, lxml.etree.ParserError) as e:
                self.warning(
                    f"legvi.org calendar for {month}/{year} unreadable "
                    f"(http {res.status_code}, {len(res.content)} bytes): {e}"
                )
                continue

            # json, embedded in html, served as a string JSON key...
            for script in page.xpath('//script[@type="application/ld+json"]'):
                row = json.loads(script.text_content())

                title = html.parser.unescape(row["name"])

                location = f"{row['location']['name']}, {row['location']['address']}"
                start = row["startDate"]
                description = row["description"]

                if "reserved" in title.lower() or "holiday" in title.lower():
                    self.info(f"Skipping {start} {title}, holiday or reserved.")
                    continue

                # some weird placeholders for location in the data
                if len(location) < 10:
                    location = "See Source"

                event = Event(
                    name=title,
                    start_date=start,
                    location_name=location,
                    description=description,
                )

                dedupe_key = f"{start}-{title}"

                # the calendar will include a few events from last month if weekdays overlap,
                # so don't double emit those.
                if dedupe_key in self.seen:
                    self.info(f"Skipping {start} - {title}, already scraped.")
                    continue
                else:
                    self.seen.append(dedupe_key)
                    event.dedupe_key = dedupe_key

                event.add_source(row["offers"]["url"])

                if row["organizer"]["name"]:
                    # todo type = Person
                    event.add_participant(row["organizer"]["name"], "person")

                if "committee" in title.lower():
                    event.add_participant(title, "committee")

                for match in re.findall(r"Bill No\.\s(\d+\-\d+)", description):
                    event.add_bill(match)

                event_count += 1
                yield event

        # LawSignals ETL-28: legvi.org answered every month of 2026 with an
        # empty calendar on 23 November 2026 (the same request returned events
        # the next day). openstates ends the WHOLE run on a scraper that returns
        # nothing, so a blank calendar cost that night's bill import too.
        # EmptyScrape is only legal when nothing was yielded, hence the count.
        if event_count == 0:
            raise EmptyScrape("legvi.org calendar returned no events")
