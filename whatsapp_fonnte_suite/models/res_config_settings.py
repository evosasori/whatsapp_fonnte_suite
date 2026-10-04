# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_aktifkan_pesan_whatsapp = fields.Boolean(
        string='Aktifkan Pengiriman WhatsApp',
        default=True,
        help='Centang opsi ini untuk mengaktifkan seluruh fitur pengiriman pesan WhatsApp pada sistem.'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_aktifkan_pesan_whatsapp = fields.Boolean(
        string='Aktifkan Pengiriman WhatsApp',
        related='company_id.is_aktifkan_pesan_whatsapp',
        readonly=False,
    )
