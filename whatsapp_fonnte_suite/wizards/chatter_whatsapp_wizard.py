# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup, escape
import re
import base64
import logging

_logger = logging.getLogger(__name__)


class ChatterWhatsappWizard(models.TransientModel):
    _name = 'chatter.whatsapp.wizard'
    _description = 'Wizard Kirim WhatsApp dari Chatter Dokumen'
    _inherit = ['fonnte.gateway']

    @api.model
    def _default_fonnte_config(self):
        config = self.env['fonnte.configuration'].sudo().search([
            ('active', '=', True),
            ('status_koneksi', '=', 'connected')
        ], limit=1)
        if not config:
            config = self.env['fonnte.configuration'].sudo().search([('active', '=', True)], limit=1)
        return config.id if config else False

    res_model = fields.Char(string='Model Dokumen', required=True)
    res_id = fields.Integer(string='ID Dokumen', required=True)

    fonnte_config_id = fields.Many2one(
        comodel_name='fonnte.configuration',
        string='Akun Fonnte Gateway',
        default=_default_fonnte_config,
        required=True
    )
    status_koneksi = fields.Selection(
        related='fonnte_config_id.status_koneksi',
        string='Status Koneksi',
        readonly=True
    )

    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Penerima (Internal User)',
        help='Pilih user Odoo untuk mengisi nomor WhatsApp secara otomatis.'
    )
    whatsapp_numbers = fields.Text(
        string='Nomor WhatsApp Tujuan',
        required=True,
        help='Daftar nomor WhatsApp tujuan (pisahkan dengan koma jika lebih dari satu nomor).'
    )
    template_id = fields.Many2one(
        comodel_name='fonnte.template',
        string='Template Pesan',
        help='Pilih template pesan WhatsApp yang telah disiapkan.'
    )
    message = fields.Text(
        string='Isi Pesan WhatsApp',
        required=True
    )
    include_doc_link = fields.Boolean(
        string='Sertakan Tautan Dokumen Odoo',
        default=True,
        help='Menyisipkan tautan langsung untuk membuka dokumen ini di browser.'
    )

    # Penanganan Lampiran Dokumen
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string='Pilih Lampiran dari Dokumen',
        help='Pilih file lampiran (PDF/Gambar) yang sudah ada pada dokumen ini untuk dikirimkan.'
    )
    upload_file = fields.Binary(string='Unggah File Baru')
    upload_filename = fields.Char(string='Nama File Unggahan')

    @api.onchange('res_model', 'res_id')
    def _onchange_res_doc(self):
        """Memuat otomatis nomor partner terkait dokumen dan daftar lampiran."""
        if not self.res_model or not self.res_id:
            return

        try:
            record = self.env[self.res_model].browse(self.res_id)
            if record.exists():
                # Cek jika ada partner_id di dokumen
                partner = getattr(record, 'partner_id', False)
                if partner:
                    num = partner.mobile or partner.phone or ''
                    if num:
                        clean_num = self._convert_to_62(num)
                        if clean_num:
                            self.whatsapp_numbers = clean_num
        except Exception as e:
            _logger.warning("Gagal mengambil nomor dari partner dokumen: %s", str(e))

    @api.onchange('user_ids')
    def _onchange_user_ids(self):
        user_numbers = []
        for user in self.user_ids:
            num = user.partner_id.mobile or user.partner_id.phone or (hasattr(user, 'mobile') and user.mobile) or ''
            clean_num = self._convert_to_62(num)
            if clean_num and clean_num not in user_numbers:
                user_numbers.append(clean_num)

        if not self.whatsapp_numbers:
            self.whatsapp_numbers = ', '.join(user_numbers)
        else:
            existing = [n.strip() for n in re.split(r'[,;\n]+', self.whatsapp_numbers) if n.strip()]
            combined = list(existing)
            for n in user_numbers:
                if n not in combined:
                    combined.append(n)
            self.whatsapp_numbers = ', '.join(combined)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id and self.res_model and self.res_id:
            try:
                record = self.env[self.res_model].browse(self.res_id)
                if record.exists():
                    self.message = self.template_id.format_message(record)
            except Exception as e:
                _logger.warning("Gagal memformat template: %s", str(e))

    def action_send_whatsapp(self):
        self.ensure_one()
        if not self.whatsapp_numbers:
            raise UserError(_("Mohon isi nomor tujuan WhatsApp."))
        if not self.message:
            raise UserError(_("Isi pesan WhatsApp tidak boleh kosong."))
        if not self.fonnte_config_id:
            raise UserError(_("Akun Fonnte Gateway belum dipilih atau belum dikonfigurasi."))

        # Pisahkan dan validasi nomor tujuan
        raw_numbers = re.split(r'[,;\n]+', self.whatsapp_numbers)
        target_numbers = [self._convert_to_62(num.strip()) for num in raw_numbers if self._convert_to_62(num.strip())]

        if not target_numbers:
            raise UserError(_("Tidak ditemukan nomor WhatsApp tujuan yang valid."))

        # Ambil referensi dokumen dan generate tautan redirect
        record = False
        doc_name = f"{self.res_model} #{self.res_id}"
        short_url = ""
        if self.res_model and self.res_id:
            try:
                record = self.env[self.res_model].browse(self.res_id)
                if record.exists():
                    doc_name = getattr(record, 'name', None) or record.display_name or doc_name
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    if base_url:
                        base_url = base_url.rstrip('/')
                        short_url = f"{base_url}/wa/d/{self.res_model}/{self.res_id}"
            except Exception as e:
                _logger.warning("Gagal menyusun URL dokumen: %s", str(e))

        # Susun format teks pesan
        pesan_bersih = self.message.strip()
        wa_text_parts = [
            "━━━━━━━━━━━━━━━━━━━━",
            "📋 NOTIFIKASI DOKUMEN",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Dokumen : {doc_name}",
            "Pesan :",
            f"*{pesan_bersih}*",
        ]
        if self.include_doc_link and short_url:
            wa_text_parts.extend([
                "━━━━━━━━━━━━━━━━━━━━",
                "👉 Buka Dokumen:",
                f"{short_url}",
            ])
        wa_text_payload = "\n".join(wa_text_parts)

        # Siapkan lampiran jika ada
        attachment_bytes = None
        attachment_filename = None

        if self.upload_file:
            attachment_bytes = base64.b64decode(self.upload_file)
            attachment_filename = self.upload_filename or 'lampiran.pdf'
        elif self.attachment_ids:
            att = self.attachment_ids[0]
            if att.datas:
                attachment_bytes = base64.b64decode(att.datas)
                attachment_filename = att.name

        targets_joined = ','.join(target_numbers)
        _logger.info("Mengirim pesan WhatsApp via Fonnte Gateway ke %s", targets_joined)

        res = self._fonnte_send_message(
            config=self.fonnte_config_id,
            target=targets_joined,
            message=wa_text_payload,
            attachment_bytes=attachment_bytes,
            filename=attachment_filename,
        )

        status_ok = res.get('status') == True
        if not status_ok:
            error_reason = res.get('reason') or res.get('message') or str(res)
            raise UserError(_("Pengiriman pesan gagal: %s") % error_reason)

        # Catat riwayat ke Chatter dokumen
        if record and record.exists():
            try:
                recipients_display = ', '.join(target_numbers)
                if self.user_ids:
                    users_name = ', '.join(self.user_ids.mapped('name'))
                    header_recipients = f"{users_name} ({recipients_display})"
                else:
                    header_recipients = recipients_display

                escaped_message = escape(pesan_bersih).replace('\n', '<br/>')
                att_html = ""
                if attachment_filename:
                    att_html = f"""
                    <div style="margin-top: 6px; font-size: 11px; color: #2d6a4f;">
                        <i class="fa fa-paperclip"></i> Lampiran Terkirim: <strong>{escape(str(attachment_filename))}</strong>
                    </div>
                    """

                link_btn_html = ""
                if self.include_doc_link and short_url:
                    link_btn_html = f"""
                    <div style="margin-top: 8px; padding-top: 6px; border-top: 1px dashed #e0e0e0;">
                        <a href="{escape(short_url)}" target="_blank" style="display: inline-block; background-color: #25D366; color: #ffffff; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: 500;">
                            <i class="fa fa-external-link" style="margin-right: 4px;"></i> Buka Dokumen ({escape(str(doc_name))})
                        </a>
                    </div>
                    """

                body_html = Markup(f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <div style="display: flex; align-items: center; margin-bottom: 6px;">
                        <span style="background-color: #25D366; color: white; border-radius: 4px; padding: 2px 8px; font-weight: bold; font-size: 11px; margin-right: 8px;">
                            <i class="fa fa-whatsapp"></i> WhatsApp Fonnte
                        </span>
                        <span style="font-size: 12px; color: #555;">Terkirim ke: <strong>{escape(header_recipients)}</strong></span>
                    </div>
                    <div style="background-color: #f8f9fa; border-left: 3px solid #25D366; padding: 8px 12px; border-radius: 4px; margin-top: 4px;">
                        <div style="color: #2b2b2b; font-size: 13px;">{escaped_message}</div>
                        {att_html}
                        {link_btn_html}
                    </div>
                </div>
                """)

                record.message_post(
                    body=body_html,
                    body_is_html=True,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=self.env.user.partner_id.id,
                )
            except Exception as e:
                _logger.error("Gagal mencatat log pesan ke Chatter: %s", str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WhatsApp Terkirim'),
                'message': _('Pesan WhatsApp berhasil dikirim ke %s nomor via Fonnte.') % len(target_numbers),
                'type': 'success',
                'sticky': False,
            }
        }
