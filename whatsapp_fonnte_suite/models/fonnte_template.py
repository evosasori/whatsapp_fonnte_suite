# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FonnteTemplate(models.Model):
    _name = 'fonnte.template'
    _description = 'Template Pesan WhatsApp Fonnte'
    _inherit = ['fonnte.gateway']

    name = fields.Char(string='Nama Template', required=True)
    code = fields.Char(string='Kode Unik', required=True)
    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model Target',
        ondelete='cascade',
        help='Pilih model dokumen (contoh: Sale Order, Invoice, Purchase Order) untuk template ini.'
    )
    model = fields.Char(related='model_id.model', string='Nama Model Teknis', readonly=True, store=True)
    body = fields.Text(
        string='Isi Template Pesan',
        required=True,
        help="Gunakan sintaks {{self.nama_field}} untuk menyisipkan nilai dokumen secara dinamis. Contoh: 'Halo {{self.partner_id.name}}, pesanan {{self.name}} telah disetujui.'"
    )
    active = fields.Boolean(string='Aktif', default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Kode template WhatsApp sudah terdaftar! Harap gunakan kode unik lain.')
    ]

    def format_message(self, record):
        """Memformat isi pesan dengan menggantikan variabel template dengan data record dokumen."""
        self.ensure_one()
        if not self.body:
            return ""
        return self._whatsapp_replace_value(self.body, record)
