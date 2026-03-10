import re
from datetime import datetime

import lxml.html
from openstates.scrape import Bill, Scraper


class VIBillScraper(Scraper):
    """
    Scraper for US Virgin Islands bill tracking site.

    As of 2026 the site moved from a JSON API on port 8082 to a
    Django/HTML application on standard HTTPS (port 443).

    Listing: POST https://billtracking.legvi.org/ with legno=<session>&pageno=<n>
    Detail:  GET  https://billtracking.legvi.org/bill_detail/<doc_entry>/
    """

    BASE_URL = "https://billtracking.legvi.org"
    verify = False

    bill_type_overrides = {
        "bill&amend": "bill",
        "bill&amp;amend": "bill",
        "lease": "contract",
        "amendment": "bill",
    }

    # Map status text from the actions table to (action_name, classification)
    action_classification = {
        "received": (None, []),
        "assigned": ("Assigned", []),
        "to senator": ("To Senate", []),
        "introduced": ("Introduced", ["introduction"]),
        "sent to lt. governor": ("Sent to Lt. Governor", ["executive-receipt"]),
        "to governor": ("Sent to Governor", ["executive-receipt"]),
        "vetoed": ("Vetoed", ["executive-veto"]),
        "approved by governor": ("Approved by Governor", ["executive-signature"]),
        "signed by governor": ("Signed by Governor", ["executive-signature"]),
        "committee action": ("Committee Action", ["committee-passage"]),
        "floor action": ("Floor Action", ["reading-3"]),
        "enacted": ("Enacted", ["became-law"]),
    }

    def scrape(self, session=None):
        # First request to get total pages
        self.info(f"Scraping VI legislature {session}")
        page_doc, total_pages = self._fetch_listing_page(session, 1)
        self.info(f"Found {total_pages} pages of bills")

        seen_ids = set()
        for page_num in range(1, total_pages + 1):
            if page_num > 1:
                page_doc, _ = self._fetch_listing_page(session, page_num)

            # Extract bill card entries from listing
            # Grid view: each card has an <a href="/bill_detail/ID/"> with bill number
            for card in page_doc.cssselect("a[href*='/bill_detail/']"):
                href = card.get("href", "")
                match = re.search(r"/bill_detail/(\d+)/", href)
                if not match:
                    continue
                doc_entry = match.group(1)
                if doc_entry in seen_ids:
                    continue
                seen_ids.add(doc_entry)

            self.info(f"Page {page_num}/{total_pages}: found {len(seen_ids)} unique bills so far")

        # Now scrape each bill detail
        for doc_entry in sorted(seen_ids):
            yield from self.scrape_bill(session, doc_entry)

    def _fetch_listing_page(self, session, page_num):
        """POST to the listing page and return (lxml doc, total_pages)."""
        data = {
            "pageno": str(page_num),
            "legno": str(session),
            "sort": "lastaction",
            "order": "desc",
        }
        resp = self.post(f"{self.BASE_URL}/", data=data, verify=False)
        doc = lxml.html.fromstring(resp.text)

        # Extract total pages from: data-total-pages="33"
        total_pages = 1
        for span in doc.cssselect("#total-pages-info"):
            tp = span.get("data-total-pages", "1")
            try:
                total_pages = int(tp)
            except ValueError:
                pass
        return doc, total_pages

    def scrape_bill(self, session, doc_entry):
        """Scrape a single bill from its detail page."""
        url = f"{self.BASE_URL}/bill_detail/{doc_entry}/"
        try:
            resp = self.get(url, verify=False)
        except Exception as e:
            self.warning(f"Failed to fetch {url}: {e}")
            return
        doc = lxml.html.fromstring(resp.text)

        # --- Extract bill identifiers from the header table ---
        # Columns: Legislature No, BR No, Bill No, Act No, Resolution No, Amendment No, Governor's No
        header_cells = doc.cssselect(
            ".bill-table tbody tr td"
        )
        if len(header_cells) < 7:
            self.warning(f"Could not parse header for {url}")
            return

        leg_no = self._cell_text(header_cells[0])
        br_no = self._cell_text(header_cells[1])
        bill_no = self._cell_link_text(header_cells[2])
        act_no = self._cell_link_text(header_cells[3])
        resolution_no = self._cell_link_text(header_cells[4])
        amendment_no = self._cell_link_text(header_cells[5])
        governor_no = self._cell_link_text(header_cells[6])

        # Determine identifier
        identifier = bill_no or resolution_no or amendment_no or governor_no
        if not identifier:
            self.warning(f"No identifier found for doc_entry {doc_entry}")
            return

        # --- Get title from the page ---
        # The title might be in a heading or we can try to get it from the status section
        # Actually the listing pages have it, but the detail page might not have a clean title.
        # Let's look for it in the page text
        title = self._extract_title(doc)
        if not title:
            title = f"VI Bill {identifier}"

        # Determine bill type
        bill_type = "bill"
        if resolution_no and not bill_no:
            bill_type = "resolution"
        elif amendment_no and not bill_no:
            bill_type = "bill"  # amendments treated as bills

        bill = Bill(
            identifier=identifier,
            legislative_session=session,
            chamber="legislature",
            title=title,
            classification=bill_type,
        )
        bill.add_source(url)

        # --- PDF links from header ---
        for cell in header_cells[2:]:
            for link in cell.cssselect("a[href*='/pdf/']"):
                link_text = link.text_content().strip()
                href = link.get("href", "")
                if href and link_text:
                    full_url = (
                        f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    )
                    bill.add_version_link(
                        link_text,
                        full_url,
                        media_type="application/pdf",
                        on_duplicate="ignore",
                    )

        # --- Sponsors from the "sponsors" tab ---
        sponsors_div = doc.cssselect("#sponsors")
        if sponsors_div:
            for row in sponsors_div[0].cssselect("tbody tr"):
                cells = row.cssselect("td")
                if len(cells) >= 2:
                    name = cells[0].text_content().strip()
                    role = cells[1].text_content().strip().lower()
                    if name:
                        is_primary = role == "primary"
                        classification = "primary" if is_primary else "cosponsor"
                        bill.add_sponsorship(
                            name,
                            classification,
                            "person",
                            primary=is_primary,
                        )

        # --- Actions from the "dates" tab ---
        dates_div = doc.cssselect("#dates")
        if dates_div:
            for row in dates_div[0].cssselect("tbody tr"):
                cells = row.cssselect("td")
                if len(cells) < 4:
                    continue

                status_text = cells[0].text_content().strip()
                date_text = cells[1].text_content().strip()
                committee = cells[2].text_content().strip()
                description = cells[3].text_content().strip()

                if not date_text or not status_text:
                    continue

                try:
                    when = datetime.strptime(date_text, "%m-%d-%Y").date()
                except ValueError:
                    try:
                        when = datetime.strptime(date_text, "%Y-%m-%d").date()
                    except ValueError:
                        self.warning(f"Bad date '{date_text}' for {identifier}")
                        continue

                # Build action description
                action_name = status_text
                classification = []

                status_lower = status_text.lower()
                for key, (mapped_name, cls) in self.action_classification.items():
                    if key in status_lower:
                        if mapped_name:
                            action_name = mapped_name
                        classification = cls
                        break

                if description and description.lower() != "none":
                    action_name = f"{action_name}: {description}"

                if committee and committee.strip() != "&nbsp;":
                    action_name = f"{action_name} ({committee})"

                bill.add_action(
                    action_name,
                    when,
                    chamber="legislature",
                    classification=classification,
                )

            # --- Document links from the actions table ---
            for row in dates_div[0].cssselect("tbody tr"):
                for link in row.cssselect(".document-cell a[href*='/pdf/']"):
                    link_text = link.text_content().strip()
                    href = link.get("href", "")
                    if href and link_text:
                        full_url = (
                            f"{self.BASE_URL}{href}"
                            if href.startswith("/")
                            else href
                        )
                        bill.add_document_link(
                            link_text,
                            full_url,
                            media_type="application/pdf",
                            on_duplicate="ignore",
                        )

        yield bill

    def _cell_text(self, cell):
        """Get text from a table cell, stripping whitespace."""
        return cell.text_content().strip()

    def _cell_link_text(self, cell):
        """Get text from a link within a cell, or the cell text if no link."""
        links = cell.cssselect("a")
        if links:
            return links[0].text_content().strip()
        text = cell.text_content().strip()
        # Ignore disabled-link spans that are empty
        if not text or text == "\xa0":
            return ""
        return text

    def _extract_title(self, doc):
        """Try to extract a bill title from the detail page.

        The new site doesn't always show a clean title field on the detail page.
        Look for descriptive text after the header table.
        """
        # Look for description in the action descriptions
        dates_div = doc.cssselect("#dates")
        if dates_div:
            for row in dates_div[0].cssselect("tbody tr"):
                cells = row.cssselect("td")
                if len(cells) >= 4:
                    desc = cells[3].text_content().strip()
                    if (
                        desc
                        and desc.lower() != "none"
                        and len(desc) > 20
                        and not desc.startswith("REPORTED")
                    ):
                        return desc
        return ""
