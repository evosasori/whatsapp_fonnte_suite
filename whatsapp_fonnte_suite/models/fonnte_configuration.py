# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class FonnteConfiguration(models.Model):
    _name = 'fonnte.configuration'
    _description = 'Konfigurasi Akun Fonnte WhatsApp Gateway'
    _inherit = ['fonnte.gateway']

    name = fields.Char(string='Nama Akun / Gateway', required=True, default='Fonnte Gateway')
    active = fields.Boolean(string='Aktif', default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Perusahaan',
        default=lambda self: self.env.company,
        required=True
    )
    is_aktifkan_pesan_whatsapp = fields.Boolean(
        string='Status Pengiriman Global',
        related='company_id.is_aktifkan_pesan_whatsapp',
        readonly=True
    )

    base_url = fields.Char(string='Base URL API', default='https://api.fonnte.com', required=True)
    token = fields.Char(string='API Token / Key', required=True)
    session_name = fields.Char(string='Nomor Pengirim / Device Session', help='Nomor WhatsApp pengirim yang terdaftar di Fonnte (opsional)')
    country_code = fields.Char(string='Default Country Code', default='62', required=True)
    delay = fields.Integer(string='Delay Antar Pesan (detik)', default=1, help='Jeda pengiriman antar nomor tujuan untuk menghindari spam/banned.')

    status_koneksi = fields.Selection(
        selection=[
            ('disconnected', 'Tidak Terhubung'),
            ('qr_ready', 'QR Siap Scan'),
            ('connected', 'Terhubung'),
        ],
        string='Status Koneksi',
        default='disconnected',
        tracking=True
    )

    device_name = fields.Char(string='Nama Device', readonly=True)
    device_number = fields.Char(string='Nomor WhatsApp Terhubung', readonly=True)
    package_type = fields.Char(string='Paket Akun', readonly=True)
    is_attachment_supported = fields.Boolean(string='Mendukung Lampiran (Media)', readonly=True)
    package_quota = fields.Char(string='Sisa Kuota Pesan', readonly=True)
    expired_date = fields.Char(string='Masa Aktif Paket', readonly=True)
    keterangan = fields.Text(string='Catatan / Respon Server')

    # Bidang pengujian pengiriman
    test_target = fields.Char(string='Nomor Target Percobaan')
    test_message = fields.Text(string='Isi Pesan Percobaan', default='Halo, ini adalah pesan uji coba dari Odoo WhatsApp Fonnte Suite!')
    test_file = fields.Binary(string='Lampiran Uji Coba')
    test_filename = fields.Char(string='Nama File Lampiran')

    def action_open_qr_wizard(self):
        """Membuka modal wizard untuk scan QR Code koneksi Fonnte."""
        self.ensure_one()
        qr_wizard = self.env['fonnte.connection.wizard'].create({
            'fonnte_config_id': self.id,
        })
        qr_wizard.action_refresh_qr()
        return {
            'name': _('Hubungkan WhatsApp (Scan QR Code)'),
            'type': 'ir.actions.act_window',
            'res_model': 'fonnte.connection.wizard',
            'res_id': qr_wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_sync_device(self):
        """Memeriksa status perangkat dan memperbarui info kuota serta nomor yang terhubung."""
        self.ensure_one()
        res = self._fonnte_get_device(self)
        _logger.info("Respon cek device Fonnte: %s", res)

        status = res.get('status')
        device_status = res.get('device_status') or ''
        
        vals = {
            'device_name': res.get('name') or False,
            'device_number': res.get('device') or False,
            'package_type': str(res.get('package') or 'Free'),
            'is_attachment_supported': bool(res.get('attachment', False)),
            'package_quota': str(res.get('quota', '')),
            'expired_date': str(res.get('expired', '')),
            'keterangan': res.get('messages') or res.get('reason') or f"Status: {device_status}",
        }

        if device_status.lower() in ['connect', 'connected'] or (status and 'connect' in str(res).lower()):
            vals['status_koneksi'] = 'connected'
        else:
            vals['status_koneksi'] = 'disconnected'

        self.write(vals)

        msg_type = 'success' if vals['status_koneksi'] == 'connected' else 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Status Perangkat Fonnte'),
                'message': _('Status: %s | Paket: %s (Media: %s) | Kuota: %s | Device: %s') % (
                    vals['status_koneksi'],
                    vals['package_type'],
                    'Ya' if vals['is_attachment_supported'] else 'Tidak',
                    vals['package_quota'],
                    vals['device_number'] or '-'
                ),
                'type': msg_type,
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    def action_disconnect(self):
        """Memutuskan sesi pairing dari Fonnte."""
        self.ensure_one()
        res = self._fonnte_disconnect(self)
        self.write({
            'status_koneksi': 'disconnected',
            'device_name': False,
            'device_number': False,
            'keterangan': res.get('reason') or res.get('message') or 'Device berhasil di-disconnect.',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WhatsApp Terputus'),
                'message': _('Koneksi WhatsApp telah diputuskan dari server Fonnte.'),
                'type': 'info',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    def action_test_send(self):
        """Menguji pengiriman pesan ke nomor target."""
        self.ensure_one()
        if not self.test_target:
            raise UserError(_("Mohon isi nomor target percobaan terlebih dahulu."))
        if not self.test_message:
            raise UserError(_("Mohon isi pesan percobaan terlebih dahulu."))

        file_bytes = base64.b64decode(self.test_file) if self.test_file else None
        res = self._fonnte_send_message(
            config=self,
            target=self.test_target,
            message=self.test_message,
            attachment_bytes=file_bytes,
            filename=self.test_filename or 'test.pdf' if file_bytes else None,
        )

        if res.get('status') == True:
            if file_bytes and not self.is_attachment_supported:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Pesan Terkirim (Lampiran Diabaikan Fonnte)'),
                        'message': _(
                            'Pesan teks terkirim, TETAPI lampiran file diabaikan oleh server Fonnte karena akun Anda adalah Paket Free '
                            '(status attachment: False). Fonnte mewajibkan paket berbayar (Super, Advanced, atau Ultra) untuk mengirimkan file media.'
                        ),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Pesan Uji Coba Terkirim!'),
                    'message': _('Respon Fonnte: %s') % str(res.get('target', 'OK')),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Fonnte merespon error: %s") % str(res.get('reason') or res))
