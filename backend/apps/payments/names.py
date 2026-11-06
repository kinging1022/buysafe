"""Does a bank account's name belong to this buysafe user?

Banks return names in any order, often with middle names and titles:
"ADEYEMI TOLU OLUWASEUN" is Tolu Adeyemi. Both names are normalised
(uppercase, accents and punctuation stripped, titles dropped), then every
word of the user's first name and last name must appear somewhere in the
bank's name. Exact string equality would reject most real accounts.
"""

import re
import unicodedata

TITLES = {
    "MR", "MRS", "MS", "MISS", "MADAM", "DR", "PROF", "ENGR", "ENG", "BARR", "ARC", "CHIEF", "ALHAJI",
    "ALHAJA", "ALH", "HAJIA", "MALLAM", "PASTOR", "REV", "REVD", "DEACON", "DCN", "ELDER", "SIR", "HON",
    "PRINCE", "PRINCESS", "OBA", "OTUNBA", "HRH", "LADY", "ESQ", "JNR", "JR", "SNR", "SR",
}


def tokens(name: str) -> list:
    """"Dr. Tolu-Ann O'Neil" -> ['TOLU', 'ANN', 'ONEIL']"""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().upper()
    text = re.sub(r"['’`]", "", text)  # O'Neil -> ONEIL, not O NEIL
    words = re.sub(r"[^A-Z]+", " ", text).split()
    return [w for w in words if w not in TITLES]


def names_match(first_name: str, last_name: str, account_name: str) -> bool:
    wanted = tokens(first_name) + tokens(last_name)
    if not tokens(first_name) or not tokens(last_name):
        return False
    have = set(tokens(account_name))
    return all(word in have for word in wanted)
