"""Pick the configured provider (settings.PAYMENTS_PROVIDER)."""

from django.conf import settings

from .anchor import AnchorTransferProvider, AnchorVirtualAccountProvider
from .base import (
    IncomingTransfer, LedgerLine, NameEnquiryError, ProviderError, TransferFailed, TransferProvider,
    TransferSucceeded, VirtualAccount, VirtualAccountProvider,
)
from .fake import FakeTransferProvider, FakeVirtualAccountProvider

_PROVIDERS = {
    "fake": (FakeVirtualAccountProvider, FakeTransferProvider),
    "anchor": (AnchorVirtualAccountProvider, AnchorTransferProvider),
}


def virtual_accounts() -> VirtualAccountProvider:
    return _PROVIDERS[settings.PAYMENTS_PROVIDER][0]()


def transfers() -> TransferProvider:
    return _PROVIDERS[settings.PAYMENTS_PROVIDER][1]()


__all__ = [
    "IncomingTransfer", "LedgerLine", "NameEnquiryError", "ProviderError", "TransferFailed", "TransferProvider",
    "TransferSucceeded", "VirtualAccount", "VirtualAccountProvider", "transfers", "virtual_accounts",
]
