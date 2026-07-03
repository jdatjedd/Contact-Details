"""
scraper/models.py

Defines the structured record produced for every scraped store, matching
the field spec:

    storeName, domain, email, emails, phone, phones,
    facebook, instagram, twitter, productCount, url, scrapedAt
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class StoreRecord:
    url: str
    domain: str = ""
    storeName: str = ""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    facebook: str = ""
    instagram: str = ""
    twitter: str = ""
    whatsapp: str = ""
    linkedin: str = ""
    address: str = ""
    contactFormUrl: str = ""
    productCount: str = "Unknown"  # "Active" | "Hidden" | "Unknown"
    score: int = 0
    pitchType: str = "Needs Review"
    scrapedAt: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    error: Optional[str] = None  # populated if the scrape failed

    @property
    def email(self) -> str:
        """Primary email = first verified/valid email found."""
        return self.emails[0] if self.emails else ""

    @property
    def phone(self) -> str:
        """Primary phone = first phone found."""
        return self.phones[0] if self.phones else ""

    def to_dict(self) -> dict:
        return {
            "storeName": self.storeName,
            "domain": self.domain,
            "email": self.email,
            "emails": ";".join(self.emails),
            "phone": self.phone,
            "phones": ";".join(self.phones),
            "facebook": self.facebook,
            "instagram": self.instagram,
            "twitter": self.twitter,
            "whatsapp": self.whatsapp,
            "linkedin": self.linkedin,
            "address": self.address,
            "contactFormUrl": self.contactFormUrl,
            "productCount": self.productCount,
            "score": self.score,
            "pitchType": self.pitchType,
            "url": self.url,
            "scrapedAt": self.scrapedAt,
        }


CSV_FIELDNAMES = [
    "storeName",
    "domain",
    "email",
    "emails",
    "phone",
    "phones",
    "facebook",
    "instagram",
    "twitter",
    "whatsapp",
    "linkedin",
    "address",
    "contactFormUrl",
    "productCount",
    "score",
    "pitchType",
    "url",
    "scrapedAt",
]
