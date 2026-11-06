"""Nigerian banks for payouts, by NIP institution code.

TODO: replace with the bank list from Anchor's GET /api/v1/banks once it's live (codes can
change, and NIP has hundreds of institutions). These are the common ones.
"""

BANKS = [
    ("000014", "Access Bank"),
    ("000010", "Ecobank"),
    ("000007", "Fidelity Bank"),
    ("000016", "First Bank"),
    ("000003", "FCMB"),
    ("000027", "Globus Bank"),
    ("000013", "GTBank"),
    ("000006", "Jaiz Bank"),
    ("000002", "Keystone Bank"),
    ("090267", "Kuda"),
    ("090405", "Moniepoint"),
    ("100004", "OPay"),
    ("100033", "PalmPay"),
    ("000008", "Polaris Bank"),
    ("000023", "Providus Bank"),
    ("000012", "Stanbic IBTC"),
    ("000001", "Sterling Bank"),
    ("000022", "SunTrust Bank"),
    ("000025", "Titan Trust Bank"),
    ("000018", "Union Bank"),
    ("000004", "UBA"),
    ("000011", "Unity Bank"),
    ("000017", "Wema Bank"),
    ("000015", "Zenith Bank"),
]

BANK_NAMES = dict(BANKS)


def bank_name(code: str) -> str:
    return BANK_NAMES.get(code, "")


def short_bank_name(name: str) -> str:
    """"Access Bank" -> "Access" (the MONEY ledger's "Access ····4521")."""
    return name[: -len(" Bank")] if name.endswith(" Bank") else name
