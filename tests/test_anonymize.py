"""
Checks for headline anonymization (src/anonymize.py).
Run (from the project root):  python3 tests/test_anonymize.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from anonymize import anonymize, load_aliases
from paths import COMPANY_NAMES, TICKERS

ALIASES = load_aliases(COMPANY_NAMES)
PASS = []


def check(name, got, expected):
    assert got == expected, f"FAIL: {name}\n  got:      {got!r}\n  expected: {expected!r}"
    PASS.append(name)
    print(f"  ok  {name}")


def anon(headline, ticker):
    return anonymize(headline, ticker, ALIASES.get(ticker, []))


print("Anonymization")
check("name + legal suffix masked",
      anon("Credit Suisse Upgrades American Airlines Group to Outperform", "AAL"),
      "Credit Suisse Upgrades the company to Outperform")
check("name with 'Inc.' and bare ticker masked",
      anon("Apple Inc. beats estimates; AAPL up 3%", "AAPL"),
      "the company beats estimates; the company up 3%")
check("cashtag masked", anon("$AAPL rallies after earnings", "AAPL"),
      "the company rallies after earnings")
check("possessive kept readable", anon("Microsoft's Azure growth slows", "MSFT"),
      "the company's Azure growth slows")
check("other companies stay visible",
      anon("Microsoft and Google battle over AI search", "MSFT"),
      "the company and Google battle over AI search")
check("no match inside other words", anon("Pineapple prices rise", "AAPL"),
      "Pineapple prices rise")
check("longest alias first", anon("Meta Platforms shares jump", "META"),
      "the company shares jump")
check("former name masked", anon("Facebook faces new probe", "META"),
      "the company faces new probe")
check("'CA' the state is left alone",
      anon("CA Technologies cuts guidance at San Jose, CA event", "CA"),
      "the company cuts guidance at San Jose, CA event")
check("unrelated headline unchanged",
      anon("Jim Cramer Gives His Opinion On JetBlue And BlackBerry", "AAL"),
      "Jim Cramer Gives His Opinion On JetBlue And BlackBerry")

missing = sorted(set(open(TICKERS).read().split()) - set(ALIASES))
check("every universe ticker has a row in company_names.csv", missing, [])

print(f"\nALL {len(PASS)} CHECKS PASSED")
