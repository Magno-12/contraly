from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class InvoiceApproval(BaseModel):
    """
    Registro de aprobaciones por diferentes roles
    """
    APPROVAL_TYPES = (
        ('REVIEW', _('Revisión')),
        ('FIRST_APPROVAL', _('Primera aprobación')),
        ('SECOND_APPROVAL', _('Segunda aprobación')),
        ('FINANCIAL_APPROVAL', _('Aprobación financiera')),
        ('FINAL_APPROVAL', _('Aprobación final')),
    )
    
    APPROVAL_RESULTS = (
        ('PENDING', _('Pendiente')),
        ('APPROVED', _('Aprobada')),
        ('REJECTED', _('Rechazada')),
        ('RETURNED', _('Devuelta para correcciones')),
    )
    
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name=_("Cuenta de cobro")
    )
    
    approval_type = models.CharField(
        max_length=30,
        choices=APPROVAL_TYPES,
        verbose_name=_("Tipo de aprobación")
    )
    
    approver = models.ForeignKey(
        'user.User',
        on_delete=models.PROTECT,
        related_name='invoice_approvals',
        verbose_name=_("Aprobador")
    )
    
    assigned_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de asignación")
    )
    
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha límite")
    )
    
    result = models.CharField(
        max_length=20,
        choices=APPROVAL_RESULTS,
        default='PENDING',
        verbose_name=_("Resultado")
    )
    
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de aprobación/rechazo")
    )
    
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Comentarios")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='invoice_approvals',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Aprobación de cuenta de cobro")
        verbose_name_plural = _("Aprobaciones de cuenta de cobro")
        ordering = ['invoice', 'approval_type', '-assigned_date']
        unique_together = [['invoice', 'approval_type', 'approver']]
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.get_approval_type_display()} - {self.get_result_display()}"
