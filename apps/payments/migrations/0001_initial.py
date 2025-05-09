# Generated by Django 4.2.9 on 2025-04-25 21:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("invoices", "0001_initial"),
        ("organizations", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=15, verbose_name="Monto pagado"
                    ),
                ),
                ("payment_date", models.DateField(verbose_name="Fecha de pago")),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Referencia de pago",
                    ),
                ),
                (
                    "is_partial",
                    models.BooleanField(default=False, verbose_name="Es pago parcial"),
                ),
                (
                    "bank_name",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Nombre del banco",
                    ),
                ),
                (
                    "account_number",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Número de cuenta",
                    ),
                ),
                (
                    "transaction_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="ID de transacción",
                    ),
                ),
                (
                    "receipt",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="payment_receipts/",
                        verbose_name="Comprobante de pago",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, null=True, verbose_name="Notas"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="invoices.invoice",
                        verbose_name="Cuenta de cobro",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pago",
                "verbose_name_plural": "Pagos",
                "ordering": ["-payment_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Withholding",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "name",
                    models.CharField(
                        max_length=100, verbose_name="Nombre de la retención"
                    ),
                ),
                ("code", models.CharField(max_length=50, verbose_name="Código")),
                (
                    "percentage",
                    models.DecimalField(
                        decimal_places=2, max_digits=6, verbose_name="Porcentaje"
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=15, verbose_name="Monto retenido"
                    ),
                ),
                (
                    "withholding_type",
                    models.CharField(
                        choices=[
                            ("TAX", "Impuesto"),
                            ("SOCIAL_SECURITY", "Seguridad social"),
                            ("PENSION", "Pensión"),
                            ("OTHER", "Otro"),
                        ],
                        default="TAX",
                        max_length=20,
                        verbose_name="Tipo de retención",
                    ),
                ),
                (
                    "certificate",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="withholding_certificates/",
                        verbose_name="Certificado de retención",
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, null=True, verbose_name="Descripción"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="withholdings",
                        to="payments.payment",
                        verbose_name="Pago",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="withholdings",
                        to="organizations.organization",
                        verbose_name="Organización",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Retención",
                "verbose_name_plural": "Retenciones",
                "ordering": ["payment", "name"],
            },
        ),
        migrations.CreateModel(
            name="PaymentStatus",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente de verificación"),
                            ("VERIFIED", "Verificado"),
                            ("REJECTED", "Rechazado"),
                            ("REFUNDED", "Reembolsado"),
                            ("CANCELLED", "Cancelado"),
                        ],
                        max_length=20,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "change_date",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Fecha de cambio"
                    ),
                ),
                (
                    "comments",
                    models.TextField(blank=True, null=True, verbose_name="Comentarios"),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_status_changes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Cambiado por",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="payments.payment",
                        verbose_name="Pago",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_statuses",
                        to="organizations.organization",
                        verbose_name="Organización",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Estado de pago",
                "verbose_name_plural": "Estados de pago",
                "ordering": ["-change_date"],
                "get_latest_by": "change_date",
            },
        ),
        migrations.CreateModel(
            name="PaymentSchedule",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("due_date", models.DateField(verbose_name="Fecha de vencimiento")),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, max_digits=15, verbose_name="Monto a pagar"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("PARTIALLY_PAID", "Parcialmente pagado"),
                            ("PAID", "Pagado"),
                            ("OVERDUE", "Vencido"),
                            ("CANCELLED", "Cancelado"),
                        ],
                        default="PENDING",
                        max_length=20,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "paid_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=15,
                        verbose_name="Monto pagado",
                    ),
                ),
                (
                    "payment_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fecha de pago"
                    ),
                ),
                (
                    "installment_number",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Número de cuota"
                    ),
                ),
                (
                    "total_installments",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Total de cuotas"
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, null=True, verbose_name="Notas"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_schedules",
                        to="invoices.invoice",
                        verbose_name="Cuenta de cobro",
                    ),
                ),
                (
                    "payments",
                    models.ManyToManyField(
                        blank=True,
                        related_name="schedules",
                        to="payments.payment",
                        verbose_name="Pagos asociados",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_schedules",
                        to="organizations.organization",
                        verbose_name="Organización",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Programación de pago",
                "verbose_name_plural": "Programaciones de pago",
                "ordering": ["invoice", "due_date"],
            },
        ),
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("name", models.CharField(max_length=100, verbose_name="Nombre")),
                (
                    "code",
                    models.CharField(max_length=50, unique=True, verbose_name="Código"),
                ),
                (
                    "description",
                    models.TextField(blank=True, null=True, verbose_name="Descripción"),
                ),
                (
                    "payment_type",
                    models.CharField(
                        choices=[
                            ("CASH", "Efectivo"),
                            ("BANK_TRANSFER", "Transferencia bancaria"),
                            ("CHECK", "Cheque"),
                            ("CREDIT_CARD", "Tarjeta de crédito"),
                            ("DEBIT_CARD", "Tarjeta de débito"),
                            ("ELECTRONIC", "Pago electrónico"),
                            ("OTHER", "Otro"),
                        ],
                        default="BANK_TRANSFER",
                        max_length=20,
                        verbose_name="Tipo de pago",
                    ),
                ),
                (
                    "requires_reference",
                    models.BooleanField(
                        default=True, verbose_name="Requiere referencia"
                    ),
                ),
                (
                    "requires_receipt",
                    models.BooleanField(
                        default=True, verbose_name="Requiere comprobante"
                    ),
                ),
                (
                    "requires_bank_info",
                    models.BooleanField(
                        default=False, verbose_name="Requiere información bancaria"
                    ),
                ),
                (
                    "allow_partial",
                    models.BooleanField(
                        default=True, verbose_name="Permite pagos parciales"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_methods",
                        to="organizations.organization",
                        verbose_name="Organización",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Método de pago",
                "verbose_name_plural": "Métodos de pago",
                "ordering": ["name"],
                "unique_together": {("code", "tenant")},
            },
        ),
        migrations.AddField(
            model_name="payment",
            name="payment_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="payments.paymentmethod",
                verbose_name="Método de pago",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="status",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="payments.paymentstatus",
                verbose_name="Estado de pago",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payments",
                to="organizations.organization",
                verbose_name="Organización",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="updated_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_updated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
