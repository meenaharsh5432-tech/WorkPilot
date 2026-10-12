from difflib import SequenceMatcher
from app.tools import invoice_tools


def find_similar_companies(company_name: str, threshold: float = 0.5) -> list[dict]:
    """Suggest company names from local invoices; never select automatically."""
    if not isinstance(company_name, str) or not company_name.strip():
        return []
    requested = company_name.strip().casefold()
    companies = set()
    # Access the module dynamically so benchmark invoice-directory overrides work.
    for path in invoice_tools.INVOICE_DIR.glob('*.txt'):
        try:
            for line in path.read_text(encoding='utf-8').splitlines():
                key, separator, value = line.partition(':')
                if separator and key.strip().casefold() == 'company':
                    if value.strip():
                        companies.add(value.strip())
                    break
        except (OSError, UnicodeError):
            continue
    matches = []
    for company in companies:
        score = SequenceMatcher(None, requested, company.casefold()).ratio()
        if score >= threshold:
            matches.append({'company': company, 'similarity': round(score, 3)})
    return sorted(matches, key=lambda item: (-item['similarity'], item['company']))[:5]
