# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import re
import base64
import requests


class FonnteConnectionWizard(models.TransientModel):
    _name = 'fonnte.connection.wizard'
    _description = 'Wizard Koneksi WhatsApp Fonnte (Scan QR)'
    _inherit = ['fonnte.gateway']

    fonnte_config_id = fields.Many2one(
        comodel_name='fonnte.configuration',
        string='Akun Konfigurasi Fonnte',
        required=True
    )
    status_koneksi = fields.Selection(
        related='fonnte_config_id.status_koneksi',
        string='Status',
        readonly=True
    )
    qr_code = fields.Binary(string='QR Code')
    keterangan = fields.Text(string='Petunjuk / Keterangan')

    def _parse_qr_base64(self, qr_raw):
        """Membersihkan format data URI dan mengembalikan bytes base64 murni."""
        if not qr_raw:
            return False
        if isinstance(qr_raw, str) and qr_raw.startswith('http'):
            # Jika Fonnte mengembalikan URL gambar langsung, unduh gambarnya
            try:
                r = requests.get(qr_raw, timeout=10)
                if r.ok:
                    return base64.b64encode(r.content)
            except Exception:
                pass
        if isinstance(qr_raw, str) and qr_raw.startswith('data:'):
            match = re.match(r'data:[^;]+;base64,(.+)', qr_raw, re.DOTALL)
            if match:
                qr_raw = match.group(1)
        return qr_raw.encode() if isinstance(qr_raw, str) else qr_raw

    def action_refresh_qr(self):
        """Mengambil QR code terbaru dari server Fonnte."""
        self.ensure_one()
        res = self._fonnte_get_qr(self.fonnte_config_id)
        status = res.get('status')

        if status == True:
            qr_raw = res.get('url')
            if qr_raw:
                self.qr_code = self._parse_qr_base64(qr_raw)
                self.keterangan = _("Silakan buka aplikasi WhatsApp di ponsel Anda > Perangkat Tertaut > Tautkan Perangkat, lalu scan QR Code di atas.")
                self.fonnte_config_id.write({'status_koneksi': 'qr_ready'})
        else:
            reason = res.get('reason') or res.get('message') or ''
            self.keterangan = reason
            if 'already connect' in reason.lower():
                self.fonnte_config_id.write({'status_koneksi': 'connected'})
                self.fonnte_config_id.action_sync_device()
                self.qr_code = False
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('WhatsApp Sudah Terhubung!'),
                        'message': _('Perangkat WhatsApp Anda sudah dalam status terhubung aktif.'),
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.client',
                            'tag': 'reload',
                        }
                    }
                }
            else:
                self.fonnte_config_id.write({'status_koneksi': 'disconnected'})
                self.qr_code = False

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_check_connection(self):
        """Memeriksa apakah scan QR telah selesai dan WhatsApp telah terhubung."""
        self.ensure_one()
        self.fonnte_config_id.action_sync_device()
        if self.fonnte_config_id.status_koneksi == 'connected':
            device_display = self.fonnte_config_id.device_number or self.fonnte_config_id.device_name or self.fonnte_config_id.name
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Berhasil Terhubung!'),
                    'message': _('WhatsApp Fonnte berhasil terkoneksi ke akun %s.') % device_display,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                    }
                }
            }
        else:
            return self.action_refresh_qr()
