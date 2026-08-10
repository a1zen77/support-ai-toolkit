from src.common.data_loader import load_tickets
import re

tickets = load_tickets()

probes = {
    'repeat-ish': re.compile(r'\bagain\b|\bstill\b|\brepeat|\bmultiple times\b', re.I),
    'dissatisfaction-ish': re.compile(r'frustrat|disappoint|unaccept|unhappy|ridiculous|unacceptable|angry|upset', re.I),
    'sla-ish': re.compile(r'\bsla\b|deadline|response time|promised|no response', re.I),
}

for label, pat in probes.items():
    hits = [t for t in tickets if pat.search(t.body)]
    print(f'{label}: {len(hits)} tickets contain rough keyword')
    for t in hits[:3]:
        print(f'   {t.ticket_id}: {t.body[:150]!r}')
    print()