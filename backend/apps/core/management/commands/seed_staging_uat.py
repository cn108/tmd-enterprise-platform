"""Build a clearly synthetic TMD UAT dataset in the isolated staging database.

This command refuses to run against any database other than ``tmd_staging``.
It uses the real procurement, inventory, accounting, invoicing, banking,
service and leasing services so the acceptance data follows application rules.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountRole,
    AccountRoleMapping,
    FiscalYear,
    JournalEntry,
)
from apps.accounting.services import (
    approve_journal,
    close_period,
    configure_retained_earnings,
    create_journal,
    post_journal,
    reverse_journal,
    submit_journal,
)
from apps.banking.models import BankAccount as CompanyBankAccount
from apps.banking.models import BankTransaction, Reconciliation
from apps.banking.services import (
    approve_reconciliation,
    import_statement,
    match_statement_line,
    submit_reconciliation,
)
from apps.catalogue.models import CatalogueItem, ItemPrice, ProductCategory, UnitOfMeasure
from apps.core.models import TaxConfiguration
from apps.identity.models import User
from apps.inventory.models import StockMovement
from apps.inventory.services import post_issue, post_stock_receipt
from apps.invoicing.models import (
    CustomerInvoice,
    CustomerInvoiceLine,
    InvoiceSettings,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    TaxTreatment,
)
from apps.invoicing.services import (
    allocate_payment,
    approve_customer_invoice,
    approve_payment,
    approve_supplier_invoice,
    recalculate_customer_invoice,
    recalculate_supplier_invoice,
    record_payment,
    submit_customer_invoice,
    submit_payment,
    submit_supplier_invoice,
)
from apps.leasing.models import (
    Equipment,
    EquipmentCategory,
    EquipmentInspection,
    EquipmentMaintenance,
    EquipmentRate,
    EquipmentReservation,
    RentalAgreement,
    RentalAgreementLine,
)
from apps.leasing.workflows import (
    approve_agreement,
    dispatch_equipment,
    rental_inspection,
    return_equipment,
)
from apps.organisation.models import CostCentre, Department
from apps.parties.models import Address, BankAccount, Contact, Party
from apps.procurement.models import (
    DeliverySchedule,
    Destination,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RfqSupplier,
    SupplierQuote,
    SupplierQuoteLine,
)
from apps.procurement.numbering import next_number
from apps.procurement.services import (
    approve_order,
    approve_request,
    issue_order,
    issue_rfq,
    open_rfq,
    receive_goods,
    select_supplier,
    submit_order,
    submit_request,
)
from apps.projects.models import (
    BudgetLine,
    CustomerContract,
    Project,
    ProjectBudget,
    ProjectCost,
    ProjectMilestone,
)
from apps.services.models import ServiceChecklistItem, ServiceContract, WorkOrder, WorkOrderReport
from apps.services.workflows import (
    accept_work_order,
    activate_contract,
    complete_work_order,
    create_contract_number,
    create_work_order_number,
    schedule_work_order,
    start_work_order,
    submit_report,
    update_progress,
)
from apps.warehousing.models import StorageLocation, Warehouse

ZERO = Decimal("0.00")
STAGING_DB = "tmd_staging"
STAGING_PASSWORD = "Tmd-Staging-2026!"  # noqa: S105 - synthetic UAT password
TODAY = date(2026, 11, 12)
PERIOD_START = date(2026, 11, 1)
PERIOD_END = date(2026, 11, 30)


class Command(BaseCommand):
    help = "Seed clearly synthetic TMD UAT records into the isolated staging database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove the synthetic UAT records before rebuilding them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != STAGING_DB:
            raise CommandError(
                f"Refusing to seed database {connection.settings_dict['NAME']!r}; "
                f"set POSTGRES_DB={STAGING_DB}."
            )

        if options["reset"]:
            self._reset()

        if Party.objects.filter(code="SUP-STG-001").exists():
            raise CommandError("Staging UAT data already exists; use --reset to rebuild it.")

        users = self._users()
        departments, centres = self._organisation(users)
        accounts = self._chart(users)
        fiscal_year, october, november = self._periods(users)
        self._configure_accounting(users, accounts)
        parties = self._parties(users)
        units, items = self._catalogue(users)
        warehouses, locations = self._warehouses(users)
        project = self._project(users, departments, centres, parties)
        purchase_order, receipt = self._procurement(
            users, departments, centres, parties, items, units, warehouses
        )
        self._inventory(users, items, units, warehouses, locations, project)
        supplier_invoice = self._payables(users, parties, purchase_order, receipt)
        self._receivables(users, parties, project, items)
        self._journals(users, accounts, fiscal_year, october, november, project, parties)
        self._payment_and_bank(users, parties, supplier_invoice)
        self._services(users, parties, project)
        self._leasing(users, parties, project)

        self._summary()

    def _reset(self):
        codes = ["SUP-STG-", "CUS-STG-", "PRJ-STG-", "ITEM-STG-", "WH-STG-", "UAT-"]
        Party.objects.filter(code__startswith="SUP-STG-").delete()
        Party.objects.filter(code__startswith="CUS-STG-").delete()
        Project.objects.filter(code__startswith="PRJ-STG-").delete()
        CatalogueItem.objects.filter(code__startswith="ITEM-STG-").delete()
        Warehouse.objects.filter(code__startswith="WH-STG-").delete()
        Equipment.objects.filter(code__startswith="EQ-STG-").delete()
        User.objects.filter(email__endswith="@staging.tmd.local").delete()
        self.stdout.write(
            self.style.WARNING("Removed prior synthetic staging records: " + ", ".join(codes))
        )

    def _user(self, email, name, role, department):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                full_name=name,
                password=STAGING_PASSWORD,
                department=department,
                must_change_password=False,
            )
        group = Group.objects.filter(name=role).first()
        if group:
            user.groups.add(group)
        return user

    def _users(self):
        departments = {
            code: Department.objects.get_or_create(code=code, defaults={"name": name})[0]
            for code, name in [
                ("OPS", "Operations"),
                ("PROC", "Procurement"),
                ("FIN", "Finance"),
                ("PRJ", "Projects"),
                ("WH", "Warehouse"),
                ("SVC", "Engineering Services"),
            ]
        }
        users = {
            "admin": User.objects.create_superuser(
                email="admin@staging.tmd.local",
                full_name="UAT System Administrator",
                password=STAGING_PASSWORD,
            )
            if not User.objects.filter(email="admin@staging.tmd.local").exists()
            else User.objects.get(email="admin@staging.tmd.local"),
        }
        users.update(
            {
                "management": self._user(
                    "management@staging.tmd.local",
                    "UAT Management",
                    "Management",
                    departments["OPS"],
                ),
                "accountant": self._user(
                    "accountant@staging.tmd.local",
                    "UAT Accountant",
                    "Accountant",
                    departments["FIN"],
                ),
                "controller": self._user(
                    "controller@staging.tmd.local",
                    "UAT Finance Controller",
                    "Finance Controller",
                    departments["FIN"],
                ),
                "finance": self._user(
                    "finance@staging.tmd.local",
                    "UAT Finance Officer",
                    "Finance Officer",
                    departments["FIN"],
                ),
                "procurement": self._user(
                    "procurement@staging.tmd.local",
                    "UAT Procurement Officer",
                    "Procurement Officer",
                    departments["PROC"],
                ),
                "project": self._user(
                    "project@staging.tmd.local",
                    "UAT Project Manager",
                    "Project Manager",
                    departments["PRJ"],
                ),
                "store": self._user(
                    "store@staging.tmd.local",
                    "UAT Storekeeper",
                    "Storekeeper",
                    departments["WH"],
                ),
                "operations": self._user(
                    "operations@staging.tmd.local",
                    "UAT Operations / HSE",
                    "Operations / HSE",
                    departments["OPS"],
                ),
                "auditor": self._user(
                    "auditor@staging.tmd.local", "UAT Auditor", "Auditor", departments["FIN"]
                ),
            }
        )
        return users

    def _organisation(self, users):
        centres = {}
        for code, name, dept in [
            ("CC-OPS-STG", "Operations staging", "OPS"),
            ("CC-PRJ-STG", "Project staging", "PRJ"),
            ("CC-WH-STG", "Warehouse staging", "WH"),
            ("CC-SVC-STG", "Service staging", "SVC"),
        ]:
            centres[code] = CostCentre.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": Department.objects.get(code=dept),
                },
            )[0]
        return {d.code: d for d in Department.objects.all()}, centres

    def _chart(self, users):
        definitions = [
            ("1000-STG", "UAT Bank", "asset", "debit"),
            ("1100-STG", "UAT Trade receivables", "asset", "debit"),
            ("1200-STG", "UAT Inventory", "asset", "debit"),
            ("1300-STG", "UAT Project cost", "asset", "debit"),
            ("2000-STG", "UAT Trade payables", "liability", "credit"),
            ("3000-STG", "UAT Share capital", "equity", "credit"),
            ("3100-STG", "UAT Opening balance equity", "equity", "credit"),
            ("3200-STG", "UAT Retained earnings", "equity", "credit"),
            ("4000-STG", "UAT Revenue", "income", "credit"),
            ("5000-STG", "UAT Cost of sales", "expense", "debit"),
            ("5100-STG", "UAT Office expenses", "expense", "debit"),
            ("5200-STG", "UAT Project materials", "expense", "debit"),
        ]
        accounts = {}
        for code, name, account_type, normal in definitions:
            account, _ = Account.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "account_type": account_type,
                    "normal_balance": normal,
                    "description": "Synthetic UAT account. Not for production.",
                    "approved_by": users["controller"],
                    "approved_at": timezone.now(),
                    "created_by": users["admin"],
                    "updated_by": users["admin"],
                },
            )
            accounts[code] = account
        roles = {
            "AR_CONTROL": "1100-STG",
            "AP_CONTROL": "2000-STG",
            "INVENTORY": "1200-STG",
            "PROJECT_COST": "1300-STG",
            "REVENUE": "4000-STG",
            "COST_OF_SALES": "5000-STG",
            "BANK": "1000-STG",
            "CASH": "1000-STG",
            "RETAINED_EARNINGS": "3200-STG",
            "OPENING_BALANCE_EQUITY": "3100-STG",
        }
        for role_code, account_code in roles.items():
            role = AccountRole.objects.filter(code=role_code).first()
            if role is None:
                continue
            AccountRoleMapping.objects.get_or_create(
                role=role,
                effective_from=date(2026, 1, 1),
                defaults={
                    "account": accounts[account_code],
                    "is_active": True,
                    "approved_by": users["controller"],
                    "approved_at": timezone.now(),
                    "notes": (
                        "Synthetic staging mapping; requires accountant review for production."
                    ),
                    "created_by": users["admin"],
                    "updated_by": users["admin"],
                },
            )
        TaxConfiguration.objects.get_or_create(
            code="UAT-VAT-075",
            defaults={
                "name": "UAT synthetic VAT 7.5% (not approved policy)",
                "tax_type": TaxConfiguration.TaxType.VAT,
                "rate": Decimal("7.5000"),
                "jurisdiction": "Nigeria (synthetic)",
                "effective_from": date(2026, 1, 1),
                "review_status": TaxConfiguration.ReviewStatus.PROVISIONAL,
                "notes": "Synthetic staging only. Not a tax instruction or production rate.",
                "created_by": users["admin"],
                "updated_by": users["admin"],
            },
        )
        TaxConfiguration.objects.get_or_create(
            code="UAT-WHT-050",
            defaults={
                "name": "UAT synthetic WHT 5% (not approved policy)",
                "tax_type": TaxConfiguration.TaxType.WHT,
                "rate": Decimal("5.0000"),
                "jurisdiction": "Nigeria (synthetic)",
                "effective_from": date(2026, 1, 1),
                "review_status": TaxConfiguration.ReviewStatus.PROVISIONAL,
                "notes": "Synthetic staging only. Not a tax instruction or production rate.",
                "created_by": users["admin"],
                "updated_by": users["admin"],
            },
        )
        InvoiceSettings.objects.update_or_create(
            pk=1,
            defaults={
                "test_mode": True,
                "company_legal_name": "TICO MCDON LIMITED (UAT SYNTHETIC)",
                "company_email": "tmdtico@gmail.com",
                "default_currency": "NGN",
                "nrs_enabled": False,
            },
        )
        return accounts

    def _periods(self, users):
        year, _ = FiscalYear.objects.get_or_create(
            code="FY2026-STG",
            defaults={
                "name": "UAT synthetic fiscal year 2026",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "created_by": users["admin"],
                "updated_by": users["admin"],
            },
        )
        october, _ = AccountingPeriod.objects.get_or_create(
            fiscal_year=year,
            name="October 2026 (UAT)",
            defaults={
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 31),
                "created_by": users["admin"],
                "updated_by": users["admin"],
            },
        )
        november, _ = AccountingPeriod.objects.get_or_create(
            fiscal_year=year,
            name="November 2026 (UAT)",
            defaults={
                "start_date": PERIOD_START,
                "end_date": PERIOD_END,
                "created_by": users["admin"],
                "updated_by": users["admin"],
            },
        )
        return year, october, november

    def _configure_accounting(self, users, accounts):
        configure_retained_earnings(accounts["3200-STG"], users["controller"])

    def _parties(self, users):
        suppliers = {}
        for code, name, terms in [
            ("SUP-STG-001", "Lagos Industrial Supply Ltd (UAT)", 30),
            ("SUP-STG-002", "Delta Engineering Services Ltd (UAT)", 14),
            ("SUP-STG-003", "Abuja Safety Works Ltd (UAT)", 21),
        ]:
            party, _ = Party.objects.get_or_create(
                code=code,
                defaults={
                    "legal_name": name,
                    "is_supplier": True,
                    "payment_terms_days": terms,
                    "default_currency": "NGN",
                    "created_by": users["procurement"],
                    "updated_by": users["procurement"],
                },
            )
            suppliers[code] = party
            Contact.objects.get_or_create(
                party=party,
                name=f"{name} contact",
                defaults={
                    "email": f"{code.lower()}@example.test",
                    "phone": "0800-UAT-0001",
                    "is_primary": True,
                    "created_by": users["procurement"],
                    "updated_by": users["procurement"],
                },
            )
            Address.objects.get_or_create(
                party=party,
                label="Registered office",
                defaults={
                    "line1": "1 Synthetic Business Way",
                    "city": "Lagos",
                    "state": "Lagos",
                    "country": "Nigeria",
                    "is_primary": True,
                    "created_by": users["procurement"],
                    "updated_by": users["procurement"],
                },
            )
        bank = BankAccount(
            supplier=suppliers["SUP-STG-001"],
            bank_name="UAT Example Bank",
            account_name="Lagos Industrial Supply Ltd (UAT)",
            created_by=users["finance"],
            updated_by=users["finance"],
        )
        bank.set_account_number("0123456789")
        bank.save()

        customers = {}
        for code, name in [
            ("CUS-STG-001", "Marina Power Company Ltd (UAT)"),
            ("CUS-STG-002", "Greenfield Estates Ltd (UAT)"),
        ]:
            customer, _ = Party.objects.get_or_create(
                code=code,
                defaults={
                    "legal_name": name,
                    "is_customer": True,
                    "credit_limit": Decimal("5000000.00"),
                    "created_by": users["project"],
                    "updated_by": users["project"],
                },
            )
            customers[code] = customer
        return {"suppliers": suppliers, "customers": customers}

    def _catalogue(self, users):
        units = {
            "EA": UnitOfMeasure.objects.get_or_create(code="EA", defaults={"name": "Each"})[0],
            "M": UnitOfMeasure.objects.get_or_create(code="M", defaults={"name": "Metre"})[0],
        }
        category = ProductCategory.objects.get_or_create(
            code="CAT-STG-ELEC", defaults={"name": "UAT electrical materials"}
        )[0]
        items = {}
        for code, name, kind, price in [
            ("ITEM-STG-PUMP", "UAT transfer pump", "product", "120000.00"),
            ("ITEM-STG-VALVE", "UAT gate valve", "product", "20000.00"),
            ("ITEM-STG-HELMET", "UAT safety helmet", "product", "15000.00"),
            ("ITEM-STG-SERVICE", "UAT engineering service", "service", "250000.00"),
        ]:
            item, _ = CatalogueItem.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "kind": kind,
                    "category": category,
                    "uom": units["EA"],
                    "description": "Fictional UAT item.",
                    "created_by": users["procurement"],
                    "updated_by": users["procurement"],
                },
            )
            items[code] = item
            ItemPrice.objects.get_or_create(
                item=item,
                currency="NGN",
                effective_from=date(2026, 1, 1),
                defaults={
                    "amount": Decimal(price),
                    "source_reference": "UAT synthetic price",
                    "created_by": users["procurement"],
                    "updated_by": users["procurement"],
                },
            )
        return units, items

    def _warehouses(self, users):
        warehouses = {}
        for code, name, site in [
            ("WH-STG-MAIN", "UAT Main Warehouse", "Lagos staging yard"),
            ("WH-STG-SITE", "UAT Marina Site Store", "Marina staging site"),
        ]:
            warehouse, _ = Warehouse.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "site_name": site,
                    "created_by": users["store"],
                    "updated_by": users["store"],
                },
            )
            warehouses[code] = warehouse
        locations = {}
        for warehouse in warehouses.values():
            location, _ = StorageLocation.objects.get_or_create(
                warehouse=warehouse,
                code="A1",
                defaults={
                    "name": "Racked bay A1",
                    "created_by": users["store"],
                    "updated_by": users["store"],
                },
            )
            locations[warehouse.code] = location
        return warehouses, locations

    def _project(self, users, departments, centres, parties):
        project, _ = Project.objects.get_or_create(
            code="PRJ-STG-001",
            defaults={
                "name": "Marina Substation Upgrade (UAT)",
                "customer": parties["customers"]["CUS-STG-001"],
                "project_manager": users["project"],
                "department": Department.objects.get(code="PRJ"),
                "cost_centre": centres["CC-PRJ-STG"],
                "status": Project.Status.ACTIVE,
                "start_date": date(2026, 9, 1),
                "end_date": date(2027, 3, 31),
                "description": "Fictional UAT project for acceptance testing.",
                "created_by": users["project"],
                "updated_by": users["project"],
            },
        )
        CustomerContract.objects.get_or_create(
            project=project,
            reference="CON-STG-001",
            defaults={
                "customer": parties["customers"]["CUS-STG-001"],
                "value": Decimal("25000000.00"),
                "currency": "NGN",
                "start_date": date(2026, 9, 1),
                "end_date": date(2027, 3, 31),
                "terms": "Synthetic UAT contract. Not a commercial commitment.",
                "created_by": users["project"],
                "updated_by": users["project"],
            },
        )
        budget, _ = ProjectBudget.objects.get_or_create(
            project=project,
            version=1,
            defaults={
                "currency": "NGN",
                "status": ProjectBudget.Status.APPROVED,
                "approved_by": users["management"],
                "approved_at": timezone.now(),
                "notes": "Synthetic UAT budget.",
                "created_by": users["project"],
                "updated_by": users["project"],
            },
        )
        for category, description, amount in [
            ("materials", "UAT electrical materials", "6000000.00"),
            ("labour", "UAT installation labour", "3500000.00"),
            ("equipment", "UAT equipment hire", "1500000.00"),
            ("logistics", "UAT transport", "1000000.00"),
        ]:
            BudgetLine.objects.get_or_create(
                budget=budget,
                description=description,
                defaults={
                    "cost_centre": centres["CC-PRJ-STG"],
                    "category": category,
                    "amount": Decimal(amount),
                    "created_by": users["project"],
                    "updated_by": users["project"],
                },
            )
        for name, due, completed in [
            ("UAT mobilisation", date(2026, 9, 15), date(2026, 9, 14)),
            ("UAT equipment delivery", date(2026, 11, 30), None),
            ("UAT commissioning", date(2027, 2, 28), None),
        ]:
            ProjectMilestone.objects.get_or_create(
                project=project,
                name=name,
                defaults={
                    "due_date": due,
                    "completed_on": completed,
                    "created_by": users["project"],
                    "updated_by": users["project"],
                },
            )
        ProjectCost.objects.get_or_create(
            project=project,
            reference="PC-STG-001",
            defaults={
                "cost_date": date(2026, 11, 5),
                "category": "logistics",
                "description": "UAT site mobilisation transport",
                "supplier": parties["suppliers"]["SUP-STG-002"],
                "amount": Decimal("300000.00"),
                "currency": "NGN",
                "status": ProjectCost.Status.APPROVED,
                "approved_by": users["management"],
                "approved_at": timezone.now(),
                "created_by": users["project"],
                "updated_by": users["project"],
            },
        )
        return project

    def _procurement(self, users, departments, centres, parties, items, units, warehouses):
        destination, _ = Destination.objects.get_or_create(
            kind=Destination.Kind.WAREHOUSE,
            warehouse=warehouses["WH-STG-MAIN"],
            defaults={"notes": "UAT warehouse destination"},
        )
        request = PurchaseRequest.objects.create(
            number=next_number("PR"),
            requester=users["operations"],
            department=Department.objects.get(code="OPS"),
            destination=destination,
            justification="Synthetic UAT procurement for acceptance testing.",
            required_by=TODAY + timedelta(days=14),
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        request_lines = {}
        for item, qty in [
            (items["ITEM-STG-PUMP"], Decimal("10.0000")),
            (items["ITEM-STG-VALVE"], Decimal("20.0000")),
        ]:
            request_lines[item.code] = PurchaseRequestLine.objects.create(
                request=request,
                item=item,
                description=item.name,
                quantity=qty,
                uom=units["EA"],
                cost_centre=centres["CC-OPS-STG"],
                created_by=users["operations"],
                updated_by=users["operations"],
            )
        submit_request(request)
        approve_request(request, users["management"])

        rfq = RequestForQuotation.objects.create(
            number=next_number("RFQ"),
            request=request,
            due_date=TODAY + timedelta(days=3),
            notes="UAT RFQ",
            created_by=users["procurement"],
            updated_by=users["procurement"],
        )
        for supplier in parties["suppliers"].values():
            RfqSupplier.objects.create(
                rfq=rfq,
                supplier=supplier,
                created_by=users["procurement"],
                updated_by=users["procurement"],
            )
        open_rfq(request, rfq)
        issue_rfq(rfq)

        quote = SupplierQuote.objects.create(
            rfq=rfq,
            supplier=parties["suppliers"]["SUP-STG-001"],
            number=next_number("QUO"),
            reference="UAT-QUOTE-001",
            received_at=TODAY,
            created_by=users["procurement"],
            updated_by=users["procurement"],
        )
        for item in [items["ITEM-STG-PUMP"], items["ITEM-STG-VALVE"]]:
            line = request_lines[item.code]
            SupplierQuoteLine.objects.create(
                quote=quote,
                request_line=line,
                quantity=line.quantity,
                unit_price=Decimal("120000.00")
                if item.code == "ITEM-STG-PUMP"
                else Decimal("20000.00"),
                lead_time_days=7,
                created_by=users["procurement"],
                updated_by=users["procurement"],
            )
        select_supplier(rfq, quote, "UAT lowest compliant synthetic quote.")

        order = PurchaseOrder.objects.create(
            number=next_number("PO"),
            supplier=parties["suppliers"]["SUP-STG-001"],
            request=request,
            rfq=rfq,
            destination=destination,
            currency="NGN",
            created_by=users["procurement"],
            updated_by=users["procurement"],
        )
        order_lines = {}
        for item in [items["ITEM-STG-PUMP"], items["ITEM-STG-VALVE"]]:
            request_line = request_lines[item.code]
            unit_price = (
                Decimal("120000.00") if item.code == "ITEM-STG-PUMP" else Decimal("20000.00")
            )
            order_line = PurchaseOrderLine.objects.create(
                order=order,
                request_line=request_line,
                item=item,
                description=item.name,
                quantity=request_line.quantity,
                unit_price=unit_price,
                uom=units["EA"],
                cost_centre=centres["CC-OPS-STG"],
                created_by=users["procurement"],
                updated_by=users["procurement"],
            )
            order_lines[item.code] = order_line
            DeliverySchedule.objects.create(
                order_line=order_line,
                due_date=TODAY + timedelta(days=10),
                quantity=request_line.quantity,
                destination=destination,
                created_by=users["procurement"],
                updated_by=users["procurement"],
            )
        submit_order(order)
        approve_order(order, users["management"])
        issue_order(order)

        receipt = receive_goods(
            order,
            users["store"],
            TODAY,
            [
                {
                    "schedule": order_lines["ITEM-STG-PUMP"].schedules.first(),
                    "order_line": order_lines["ITEM-STG-PUMP"],
                    "quantity_delivered": Decimal("5"),
                    "quantity_accepted": Decimal("4"),
                    "quantity_damaged": Decimal("1"),
                    "rejection_reason": "UAT: one pump damaged in transit.",
                },
                {
                    "schedule": order_lines["ITEM-STG-VALVE"].schedules.first(),
                    "order_line": order_lines["ITEM-STG-VALVE"],
                    "quantity_delivered": Decimal("10"),
                    "quantity_accepted": Decimal("10"),
                },
            ],
            notes="UAT partial delivery with one damaged pump.",
        )
        return order, receipt

    def _inventory(self, users, items, units, warehouses, locations, project):
        post_stock_receipt(
            warehouse=warehouses["WH-STG-MAIN"],
            supplier=None,
            received_at=date(2026, 11, 1),
            reference="UAT-OPENING-STOCK",
            notes="Synthetic UAT opening stock. Not a production opening balance.",
            lines=[
                {
                    "item": items["ITEM-STG-PUMP"],
                    "quantity": Decimal("5"),
                    "unit_cost": Decimal("120000"),
                },
                {
                    "item": items["ITEM-STG-VALVE"],
                    "quantity": Decimal("10"),
                    "unit_cost": Decimal("20000"),
                },
                {
                    "item": items["ITEM-STG-HELMET"],
                    "quantity": Decimal("5"),
                    "unit_cost": Decimal("15000"),
                },
            ],
            actor=users["store"],
        )
        post_issue(
            project=project,
            cost_centre=project.cost_centre,
            recipient="UAT site team",
            notes="UAT project material issue.",
            lines=[
                {
                    "item": items["ITEM-STG-PUMP"],
                    "warehouse": warehouses["WH-STG-MAIN"],
                    "location": locations["WH-STG-MAIN"],
                    "quantity": Decimal("2"),
                }
            ],
            actor=users["store"],
        )

    def _payables(self, users, parties, order, receipt):
        invoice = SupplierInvoice.objects.create(
            number=next_number("SI"),
            supplier_invoice_number="UAT-SINV-001",
            supplier=parties["suppliers"]["SUP-STG-001"],
            purchase_order=order,
            invoice_date=TODAY,
            due_date=TODAY + timedelta(days=30),
            currency="NGN",
            is_test=True,
            notes="Synthetic UAT supplier invoice.",
            created_by=users["finance"],
            updated_by=users["finance"],
        )
        for order_line in order.lines.select_related("item"):
            receipt_line = receipt.lines.filter(order_line=order_line).first()
            if receipt_line is None:
                continue
            SupplierInvoiceLine.objects.create(
                invoice=invoice,
                order_line=order_line,
                receipt_line=receipt_line,
                item=order_line.item,
                description=order_line.description,
                quantity=receipt_line.quantity_accepted,
                unit_price=order_line.unit_price,
                tax_treatment=TaxTreatment.EXEMPT,
                subtotal=receipt_line.quantity_accepted * order_line.unit_price,
                total=receipt_line.quantity_accepted * order_line.unit_price,
                created_by=users["finance"],
                updated_by=users["finance"],
            )
        recalculate_supplier_invoice(invoice)
        submit_supplier_invoice(invoice, users["finance"])
        approve_supplier_invoice(invoice, users["controller"])
        return invoice

    def _receivables(self, users, parties, project, items):
        invoice = CustomerInvoice.objects.create(
            number=next_number("CI"),
            customer=parties["customers"]["CUS-STG-001"],
            project=project,
            customer_reference="UAT-CUST-REF-001",
            invoice_date=TODAY,
            due_date=TODAY + timedelta(days=30),
            currency="NGN",
            is_test=True,
            notes="Synthetic UAT customer invoice.",
            created_by=users["finance"],
            updated_by=users["finance"],
        )
        CustomerInvoiceLine.objects.create(
            invoice=invoice,
            item=items["ITEM-STG-SERVICE"],
            description="UAT substation engineering milestone",
            quantity=Decimal("1"),
            unit_price=Decimal("2500000.00"),
            tax_treatment=TaxTreatment.EXEMPT,
            subtotal=Decimal("2500000.00"),
            total=Decimal("2500000.00"),
            created_by=users["finance"],
            updated_by=users["finance"],
        )
        recalculate_customer_invoice(invoice)
        submit_customer_invoice(invoice, users["finance"])
        approve_customer_invoice(invoice, users["controller"])
        return invoice

    def _payment_and_bank(self, users, parties, invoice):
        company_account, _ = CompanyBankAccount.objects.get_or_create(
            code="BANK-STG-001",
            defaults={
                "name": "UAT operating account",
                "bank_name": "UAT Example Bank",
                "branch": "Lagos staging",
                "account_name": "TICO MCDON LIMITED (UAT)",
                "account_last4": "6789",
                "currency": "NGN",
                "classification": CompanyBankAccount.Classification.OPERATING,
                "opening_balance": Decimal("4675000.00"),
                "opening_balance_date": date(2026, 11, 1),
                "gl_account": Account.objects.get(code="1000-STG"),
                "notes": "Synthetic UAT bank account.",
                "created_by": users["finance"],
                "updated_by": users["finance"],
            },
        )
        supplier_account = BankAccount.objects.get(supplier=parties["suppliers"]["SUP-STG-001"])
        payment = SupplierPayment.objects.create(
            number=next_number("PAY"),
            supplier=parties["suppliers"]["SUP-STG-001"],
            payment_date=TODAY,
            currency="NGN",
            amount=Decimal("500000.00"),
            method=SupplierPayment.Method.BANK_TRANSFER,
            external_reference="UAT-PAY-001",
            bank_account=supplier_account,
            company_bank_account=company_account,
            is_test=True,
            notes="Synthetic UAT payment; no bank transfer was executed.",
            created_by=users["finance"],
            updated_by=users["finance"],
        )
        submit_payment(payment, users["finance"])
        approve_payment(payment, users["controller"])
        record_payment(payment, users["finance"], idempotency_key="uat-payment-001")
        allocate_payment(payment, invoice, Decimal("500000.00"), users["finance"])

        charge = BankTransaction.objects.create(
            number=next_number("BTX"),
            bank_account=company_account,
            transaction_date=TODAY,
            description="UAT bank charge",
            reference="UAT-BANK-CHARGE",
            currency="NGN",
            amount=Decimal("-15000.00"),
            source_type=BankTransaction.Source.BANK_CHARGE,
            status=BankTransaction.Status.RECORDED,
            created_by=users["finance"],
            updated_by=users["finance"],
        )

        statement_bytes = (
            "Date,Description,Reference,Debit,Credit,Balance\n"
            f"2026-11-12,Supplier payment UAT,{payment.number},500000.00,,4175000.00\n"
            "2026-11-12,UAT bank charge,UAT-BANK-CHARGE,15000.00,,4160000.00\n"
        ).encode()
        upload = SimpleUploadedFile(
            "uat-bank-statement-2026-11.csv", statement_bytes, content_type="text/csv"
        )
        statement = import_statement(
            bank_account=company_account,
            upload=upload,
            user=users["finance"],
            validated={
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "opening_balance": Decimal("4675000.00"),
                "closing_balance": Decimal("4160000.00"),
                "reference": "UAT November statement",
                "currency": "NGN",
            },
        )
        payment_line = statement.lines.get(reference=payment.number)
        payment_transaction = BankTransaction.objects.get(
            source_type=BankTransaction.Source.SUPPLIER_PAYMENT, source_id=payment.pk
        )
        match_statement_line(
            line=payment_line,
            reconciliation=statement.reconciliation,
            transaction=payment_transaction,
            amount=Decimal("500000.00"),
            match_type="one_to_one",
            user=users["finance"],
            notes="UAT exact reference and amount match.",
        )
        charge_line = statement.lines.get(reference="UAT-BANK-CHARGE")
        match_statement_line(
            line=charge_line,
            reconciliation=statement.reconciliation,
            transaction=charge,
            amount=Decimal("15000.00"),
            match_type="one_to_one",
            user=users["finance"],
            notes="UAT bank charge matched to the posted charge journal.",
        )
        submit_reconciliation(statement.reconciliation, users["finance"])
        approve_reconciliation(statement.reconciliation, users["controller"])
        return payment, company_account

    def _post(
        self, *, actor, approver, date_, period, description, lines, source="manual", reason=""
    ):
        journal = create_journal(
            journal_date=date_,
            period=period,
            description=description,
            lines=lines,
            actor=actor,
            source_type=source,
            reason=reason,
        )
        submit_journal(journal, actor)
        approve_journal(journal, approver)
        return post_journal(journal, actor)

    def _journals(self, users, accounts, fiscal_year, october, november, project, parties):
        a = accounts
        october_expense = self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=date(2026, 10, 20),
            period=october,
            description="UAT October office expense",
            lines=[
                {"account": a["5100-STG"], "debit": Decimal("25000.00"), "credit": ZERO},
                {"account": a["1000-STG"], "debit": ZERO, "credit": Decimal("25000.00")},
            ],
        )
        close_period(october, users["controller"])
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=date(2026, 11, 1),
            period=november,
            description="UAT synthetic opening capital",
            lines=[
                {"account": a["1000-STG"], "debit": Decimal("5000000.00"), "credit": ZERO},
                {"account": a["3000-STG"], "debit": ZERO, "credit": Decimal("5000000.00")},
            ],
        )
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=date(2026, 11, 2),
            period=november,
            description="UAT opening stock contribution",
            lines=[
                {"account": a["1200-STG"], "debit": Decimal("1555000.00"), "credit": ZERO},
                {"account": a["2000-STG"], "debit": ZERO, "credit": Decimal("680000.00")},
                {"account": a["3100-STG"], "debit": ZERO, "credit": Decimal("875000.00")},
            ],
        )
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=TODAY,
            period=november,
            description="UAT supplier payment",
            lines=[
                {"account": a["2000-STG"], "debit": Decimal("500000.00"), "credit": ZERO},
                {"account": a["1000-STG"], "debit": ZERO, "credit": Decimal("500000.00")},
            ],
        )
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=date(2026, 11, 6),
            period=november,
            description="UAT project material issue",
            lines=[
                {"account": a["1300-STG"], "debit": Decimal("240000.00"), "credit": ZERO},
                {"account": a["1200-STG"], "debit": ZERO, "credit": Decimal("240000.00")},
            ],
        )
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=date(2026, 11, 5),
            period=november,
            description="UAT direct project cost",
            lines=[
                {"account": a["1300-STG"], "debit": Decimal("300000.00"), "credit": ZERO},
                {"account": a["1000-STG"], "debit": ZERO, "credit": Decimal("300000.00")},
            ],
        )
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=TODAY,
            period=november,
            description="UAT customer invoice revenue",
            lines=[
                {"account": a["1100-STG"], "debit": Decimal("2500000.00"), "credit": ZERO},
                {"account": a["4000-STG"], "debit": ZERO, "credit": Decimal("2500000.00")},
            ],
        )
        # Prove reversal is a separate posted journal, then post a small bank charge.
        charge = self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=TODAY,
            period=november,
            description="UAT bank charge subject to reversal",
            lines=[
                {"account": a["5100-STG"], "debit": Decimal("10000.00"), "credit": ZERO},
                {"account": a["1000-STG"], "debit": ZERO, "credit": Decimal("10000.00")},
            ],
        )
        reverse_journal(charge, users["controller"], "UAT synthetic reversal test")
        self._post(
            actor=users["accountant"],
            approver=users["controller"],
            date_=TODAY,
            period=november,
            description="UAT bank charge after reversal",
            lines=[
                {"account": a["5100-STG"], "debit": Decimal("15000.00"), "credit": ZERO},
                {"account": a["1000-STG"], "debit": ZERO, "credit": Decimal("15000.00")},
            ],
        )
        return october_expense

    def _services(self, users, parties, project):
        contract = ServiceContract.objects.create(
            number=create_contract_number(),
            customer=parties["customers"]["CUS-STG-001"],
            project=project,
            kind=ServiceContract.Kind.ENGINEERING,
            title="UAT substation engineering support",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 3, 31),
            value=Decimal("1800000.00"),
            status=ServiceContract.Status.DRAFT,
            terms="Synthetic UAT service contract.",
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        activate_contract(contract, users["management"])
        work_order = WorkOrder.objects.create(
            number=create_work_order_number(),
            service_contract=contract,
            project=project,
            customer=parties["customers"]["CUS-STG-001"],
            request_type=WorkOrder.RequestType.INSTALLATION,
            priority=WorkOrder.Priority.HIGH,
            status=WorkOrder.Status.DRAFT,
            title="UAT transformer installation support",
            description="Synthetic UAT work order.",
            site="Marina staging site",
            supervisor=users["project"],
            requested_by=users["operations"],
            hse_requirements="UAT isolation and PPE checklist",
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        schedule_work_order(
            work_order,
            users["operations"],
            start=date(2026, 11, 10),
            end=date(2026, 11, 14),
        )
        start_work_order(work_order, users["operations"], started_on=date(2026, 11, 10))
        update_progress(
            work_order,
            users["operations"],
            percent=60,
            notes="UAT synthetic progress.",
            labour_hours=Decimal("12.00"),
            materials_used="UAT cable and glands",
        )
        ServiceChecklistItem.objects.create(
            work_order=work_order,
            sequence=1,
            description="UAT isolation and PPE checklist",
            is_required=True,
            is_completed=True,
            completed_by=users["operations"],
            completed_at=timezone.now(),
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        report = WorkOrderReport.objects.create(
            work_order=work_order,
            summary="UAT installation support completed. Synthetic record.",
            findings="No real findings.",
            recommendations="Proceed to UAT acceptance.",
            completed_on=date(2026, 11, 12),
            status=WorkOrderReport.Status.DRAFT,
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        submit_report(report, users["operations"])
        complete_work_order(work_order, users["operations"])
        accept_work_order(
            work_order, users["management"], representative="UAT Customer Representative"
        )
        return contract, work_order

    def _leasing(self, users, parties, project):
        category = EquipmentCategory.objects.get_or_create(
            code="EQCAT-STG", defaults={"name": "UAT test equipment"}
        )[0]
        equipment = Equipment.objects.create(
            code="EQ-STG-GEN-001",
            name="UAT 100 kVA generator",
            category=category,
            serial_number="UAT-SN-GEN-001",
            ownership=Equipment.Ownership.OWNED,
            location="UAT main yard",
            asset_classification="UAT synthetic",
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        second = Equipment.objects.create(
            code="EQ-STG-COMP-001",
            name="UAT air compressor",
            category=category,
            serial_number="UAT-SN-COMP-001",
            ownership=Equipment.Ownership.OWNED,
            location="UAT main yard",
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        rate = EquipmentRate.objects.create(
            equipment=equipment,
            basis=EquipmentRate.Basis.DAILY,
            amount=Decimal("85000.00"),
            currency="NGN",
            effective_from=date(2026, 1, 1),
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        EquipmentReservation.objects.create(
            equipment=second,
            customer=parties["customers"]["CUS-STG-002"],
            start_date=date(2026, 11, 20),
            end_date=date(2026, 11, 22),
            quantity=Decimal("1"),
            status=EquipmentReservation.Status.CONFIRMED,
            notes="UAT tentative reservation.",
            created_by=users["project"],
            updated_by=users["project"],
        )
        agreement = RentalAgreement.objects.create(
            number=next_number("RA"),
            customer=parties["customers"]["CUS-STG-001"],
            project=project,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 14),
            currency="NGN",
            status=RentalAgreement.Status.SUBMITTED,
            terms="Synthetic UAT rental.",
            requested_by=users["project"],
            created_by=users["project"],
            updated_by=users["project"],
        )
        RentalAgreementLine.objects.create(
            agreement=agreement,
            equipment=equipment,
            rate=rate,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 14),
            quantity=Decimal("1"),
            rate_amount=Decimal("85000.00"),
            created_by=users["project"],
            updated_by=users["project"],
        )
        approve_agreement(agreement, users["management"])
        dispatch_equipment(
            agreement,
            users["store"],
            equipment=equipment,
            on_date=date(2026, 11, 10),
            condition="good",
            expected_return=date(2026, 11, 14),
            notes="UAT dispatch.",
        )
        return_equipment(
            agreement,
            users["store"],
            equipment=equipment,
            on_date=date(2026, 11, 12),
            condition="good",
            notes="UAT return.",
        )
        inspection = EquipmentInspection.objects.create(
            equipment=equipment,
            agreement=agreement,
            kind=EquipmentInspection.Kind.RETURN,
            inspection_date=date(2026, 11, 12),
            condition="good",
            damage_found=False,
            inspected_by=users["operations"],
            notes="UAT return inspection.",
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        rental_inspection(inspection, users["operations"])
        agreement.status = RentalAgreement.Status.CLOSED
        agreement.closed_at = timezone.now()
        agreement.updated_by = users["store"]
        agreement.save(update_fields=["status", "closed_at", "updated_by", "updated_at"])
        EquipmentMaintenance.objects.create(
            equipment=second,
            kind=EquipmentMaintenance.Kind.PREVENTIVE,
            scheduled_date=date(2026, 11, 25),
            status=EquipmentMaintenance.Status.PLANNED,
            description="UAT synthetic preventive maintenance.",
            vendor="UAT vendor",
            cost=Decimal("45000.00"),
            created_by=users["operations"],
            updated_by=users["operations"],
        )
        return agreement

    def _summary(self):
        self.stdout.write(self.style.SUCCESS("Synthetic TMD UAT staging data created."))
        for label, model in [
            ("users", User.objects.filter(email__endswith="@staging.tmd.local")),
            (
                "suppliers/customers",
                Party.objects.filter(
                    Q(code__startswith="SUP-STG-") | Q(code__startswith="CUS-STG-")
                ),
            ),
            ("projects", Project.objects.filter(code__startswith="PRJ-STG-")),
            ("catalogue items", CatalogueItem.objects.filter(code__startswith="ITEM-STG-")),
            ("warehouses", Warehouse.objects.filter(code__startswith="WH-STG-")),
            ("purchase orders", PurchaseOrder.objects.all()),
            ("stock movements", StockMovement.objects.all()),
            ("journals", JournalEntry.objects.all()),
            ("supplier invoices", SupplierInvoice.objects.all()),
            ("customer invoices", CustomerInvoice.objects.all()),
            ("bank reconciliations", Reconciliation.objects.all()),
            ("work orders", WorkOrder.objects.all()),
            ("rental agreements", RentalAgreement.objects.all()),
        ]:
            self.stdout.write(f"  {label}: {model.count()}")
