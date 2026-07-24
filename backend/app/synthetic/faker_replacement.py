"""Document-seeded, consistent synthetic replacements kept only in memory."""

from __future__ import annotations

import hashlib
import random
import re
from datetime import date, timedelta
import calendar
from dateutil import parser as date_parser

from faker import Faker

from app.detection.types import DetectionCandidate, DetectionDecision


class SyntheticReplacementEngine:
    """Generate plausible values consistently within one document."""

    def __init__(self, document_seed: str) -> None:
        digest = hashlib.sha256(document_seed.encode("utf-8")).digest()
        self._seed = int.from_bytes(digest[:8], "big")
        self._faker = Faker("en_US")
        self._faker.seed_instance(self._seed)
        self._random = random.Random(self._seed)
        self._cache: dict[tuple[str, str], str] = {}

    def assign(self, candidates: list[DetectionCandidate]) -> set[str]:
        replacements: set[str] = set()
        for candidate in candidates:
            if candidate.decision != DetectionDecision.AUTO_REDACT:
                continue
            replacement = self.for_value(candidate.entity_type, candidate.matched_text)
            candidate.replacement_text = replacement
            replacements.add(replacement)
        return replacements

    def for_value(self, entity_type: str, original: str) -> str:
        key = (entity_type, original.casefold())
        if key not in self._cache:
            self._cache[key] = self._generate(entity_type, original)
        return self._cache[key]

    def _generate(self, entity_type: str, original: str) -> str:
        kind = entity_type.upper()
        if kind in {"PERSON", "PATIENT_NAME"}:
            lowered = original.casefold().strip()
            if lowered.startswith(("mr ", "mr. ")):
                return f"Mr. {self._faker.name_male()}"
            if lowered.startswith(("mrs ", "mrs. ", "ms ", "ms. ", "miss ")):
                return f"Ms. {self._faker.name_female()}"
            return self._faker.name()
        if kind == "EMAIL_ADDRESS":
            return self._faker.email()
        if kind == "PHONE_NUMBER":
            return self._faker.numerify("###-###-####")
        if kind in {"LOCATION", "NRP"}:
            return self._faker.city()
        if kind in {"DATE_TIME", "DOB", "BILLING_DATE"}:
            return self._shifted_date(original)
        if kind in {"NPI", "US_NPI"}:
            return self._valid_npi()
        if kind in {"MRN", "INSURANCE_ID", "POLICY_NUMBER", "PAYER_ID"}:
            return f"SYN-{self._faker.bothify('??########').upper()}"
        if kind in {"US_SSN", "US_ITIN"}:
            return self._faker.numerify("9##-7#-####")
        if kind in {"MEDICAL_CONDITION", "MEDICATION", "CLINICAL_ENTITY"}:
            return f"[SYNTHETIC {kind.replace('_', ' ')}]"
        return f"[SYNTHETIC {kind}]"

    def _shifted_date(self, original: str) -> str:
        try:
            parsed = date_parser.parse(original, fuzzy=False, dayfirst=False).date()
        except (ValueError, OverflowError):
            shifted = date.today() - timedelta(days=self._random.randint(30, 3650))
            return shifted.isoformat()
        season_months = {
            1: (12,), 2: (1, 2), 3: (3, 4, 5),
            4: (6, 7, 8), 5: (9, 10, 11),
        }[1 if parsed.month == 12 else 2 if parsed.month <= 2 else 3 if parsed.month <= 5 else 4 if parsed.month <= 8 else 5]
        month = self._random.choice(season_months)
        year = parsed.year
        day = min(self._random.randint(1, 28), calendar.monthrange(year, month)[1])
        replacement = date(year, month, day)
        today = date.today()
        original_age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
        replacement_age = today.year - replacement.year - ((today.month, today.day) < (replacement.month, replacement.day))
        if replacement_age != original_age:
            replacement = replacement.replace(year=replacement.year + replacement_age - original_age)
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", original.strip()):
            return replacement.isoformat()
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", original.strip()):
            return replacement.strftime("%m/%d/%Y" if len(original.rsplit("/", 1)[-1]) == 4 else "%m/%d/%y")
        if re.search(r"[A-Za-z]", original):
            return replacement.strftime("%B %d, %Y")
        return replacement.isoformat()

    def _valid_npi(self) -> str:
        base = "1" + "".join(str(self._random.randrange(10)) for _ in range(8))
        digits = [int(value) for value in "80840" + base]
        total = 0
        parity = len(digits) % 2
        for index, value in enumerate(digits):
            if index % 2 == parity:
                value *= 2
                if value > 9:
                    value -= 9
            total += value
        return base + str((10 - total % 10) % 10)
