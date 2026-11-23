import json
import pytest
from pydantic import ValidationError

from src.models import Bill, Parameters, TenantSettlement, ApartmentSettlement, Transfer
from src.manager import Manager


def test_settlement_due_between_tanants_and_apartment():
    manager = Manager(Parameters())

    settlement: ApartmentSettlement = manager.get_settlement('apart-polanka', 2025, 1)
    
    tenants_settlements: list[TenantSettlement] = manager.create_tenants_settlements(settlement)
    assert len(tenants_settlements) == 3

    total_due = sum([tenant_settlement.total_due_pln for tenant_settlement in tenants_settlements])
    assert total_due == settlement.total_due_pln

def test_debtors_calculation():
    manager = Manager(Parameters())

    debtors = manager.get_debtors('apart-polanka', 2025, 1)
    assert len(debtors) == 0

    debtors = manager.get_debtors('apart-polanka', 2025, 2)
    assert len(debtors) == 3


def test_tax_calculation():
    manager = Manager(Parameters())
    
    tax = manager.calculate_tax(2025, 1, 0.085)
    assert tax == 638 # 0.085 * 7500.0

    tax = manager.calculate_tax(2025, 2, 0.085)
    assert tax == 0

def test_deposits_calculation():
    manager = Manager(Parameters())
    
    deposit_balance = manager.check_deposits()
    assert deposit_balance == -8700.0 # no deposit in transfers

    manager.transfers.append(Transfer(
        tenant='tenant-1',
        date='2025-01-01',
        settlement_year=None,
        settlement_month=None,
        amount_pln=1000.0,
        type='deposit'
    ))

    deposit_balance = manager.check_deposits()
    assert deposit_balance == -7700.0 # 1000.0 deposit in transfers

def test_annual_balance_calculation():
    manager = Manager(Parameters())
    
    annual_balance = manager.get_annual_balance(2025)
    assert annual_balance == 6490.0 # 7500.0 in transfers minus 910.0 in bills

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-02-15',
        settlement_year=2025,
        settlement_month=5,
        amount_pln=500.0,
        type='rent'
    ))

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-02-15',
        settlement_year=2025,
        settlement_month=5,
        amount_pln=4500.0,
        type='renovation'
    ))

    annual_balance = manager.get_annual_balance(2025)
    assert annual_balance == 1490.0 # 7500.0 in transfers minus 910.0 in bills minus new bills 500.0 and 4500.0

def test_apartment_has_any_bills():
    manager = Manager(Parameters())
    
    has_bills = manager.has_any_bills('apart-polanka', 2025, 1)
    assert has_bills == True

    has_bills = manager.has_any_bills('apart-polanka', 2025, 3)
    assert has_bills == False


def test_blacklist_model_and_default_file_loading():
    """Verify BlacklistedTenant model validation and default blacklist.json loading."""
    from src.models import BlacklistedTenant

    entry = BlacklistedTenant(name="Marek Kowalczyk", reason="Nieplacenie czynszu")
    assert entry.name == "Marek Kowalczyk"
    assert entry.reason == "Nieplacenie czynszu"

    with pytest.raises(ValidationError):
        BlacklistedTenant(name="Marek Kowalczyk")

    with pytest.raises(ValidationError):
        BlacklistedTenant(name=123, reason="Nieplacenie czynszu")

    params = Parameters()
    assert params.blacklist_json_path == 'data/blacklist.json'

    manager = Manager(params)
    assert isinstance(manager.blacklist, list)
    assert len(manager.blacklist) > 0
    for item in manager.blacklist:
        assert isinstance(item, BlacklistedTenant)
        assert isinstance(item.name, str) and len(item.name.strip()) > 0
        assert isinstance(item.reason, str) and len(item.reason.strip()) > 0

    assert manager.is_tenant_blacklisted(manager.blacklist[0].name) is True


def test_blacklist_check_from_custom_file(tmp_path):
    """Verify loading blacklist from a custom JSON file and checking tenants."""
    from src.models import BlacklistedTenant

    blacklist_data = [
        {"name": "Marek Kowalczyk", "reason": "Nieplacenie czynszu"},
        {"name": "Anna Zielinska", "reason": "Zniszczenie mienia"},
    ]
    blacklist_file = tmp_path / "blacklist.json"
    blacklist_file.write_text(json.dumps(blacklist_data), encoding="utf-8")

    manager = Manager(Parameters(blacklist_json_path=str(blacklist_file)))
    assert len(manager.blacklist) == 2
    assert isinstance(manager.blacklist[0], BlacklistedTenant)
    assert manager.blacklist[0].name == "Marek Kowalczyk"
    assert manager.blacklist[0].reason == "Nieplacenie czynszu"

    assert manager.is_tenant_blacklisted("Marek Kowalczyk") is True
    assert manager.is_tenant_blacklisted("Anna Zielinska") is True
    assert manager.is_tenant_blacklisted("marek kowalczyk") is True
    assert manager.is_tenant_blacklisted("Jan Nowak") is False
    assert manager.is_tenant_blacklisted("") is False


def test_blacklist_dynamic_updates():
    """Verify is_tenant_blacklisted reflects updates to manager.blacklist."""
    from src.models import BlacklistedTenant

    manager = Manager(Parameters())
    manager.blacklist = []
    assert manager.is_tenant_blacklisted("Piotr Testowy") is False

    manager.blacklist.append(
        BlacklistedTenant(name="Piotr Testowy", reason="Zaklocanie ciszy nocnej")
    )
    assert manager.is_tenant_blacklisted("Piotr Testowy") is True
