# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FonnteValidateWizard(models.TransientModel):
    _name = 'fonnte.validate.wizard'
    _description = 'Wizard Validasi Nomor WhatsApp Fonnte'
    _inherit = ['fonnte.gateway']

    @api.model
    def _default_fonnte_config(self):
        return self.env['fonnte.configuration'].search([('active', '=', True)], limit=1).id

    fonnte_config_id = fields.Many2one(
        comodel_name='fonnte.configuration',
        string='Akun Konfigurasi Fonnte',
        default=_default_fonnte_config,
        required=True
    )
    phone_number = fields.Char(string='Nomor WhatsApp', required=True)
    country_code = fields.Char(string='Country Code', default='62')
    result_status = fields.Selection(
        selection=[
            ('pending', 'Belum Diperiksa'),
            ('valid', 'Terdaftar di WhatsApp'),
            ('invalid', 'Tidak Terdaftar di WhatsApp'),
        ],
        string='Hasil Pemeriksaan',
        default='pending',
        readonly=True
    )
    result_message = fields.Text(string='Detail Respon Server', readonly=True)

    def action_validate_phone(self):
        self.ensure_one()
        if not self.phone_number:
            raise UserError(_("Mohon isi nomor telepon yang ingin divalidasi."))

        res = self._fonnte_validate_phone(
            config=self.fonnte_config_id,
            target=self.phone_number,
            country_code=self.country_code
        )

        status = res.get('status')
        # Format Fonnte: status=True/False, registered=True/False atau reason
        is_registered = res.get('registered') or (status and 'valid' in str(res).lower())

        if is_registered:
            self.write({
                'result_status': 'valid',
                'result_message': _("Nomor %s TERDAFTAR aktif di WhatsApp.") % self.phone_number,
            })
        else:
            self.write({
                'result_status': 'invalid',
                'result_message': res.get('reason') or res.get('message') or _("Nomor tidak terdaftar atau tidak aktif di WhatsApp."),
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
