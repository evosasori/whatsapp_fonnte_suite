# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import re
import logging
import base64

_logger = logging.getLogger(__name__)


class FonnteGateway(models.AbstractModel):
    _name = 'fonnte.gateway'
    _description = 'Fonnte WhatsApp API Gateway'

    @api.model
    def _convert_to_62(self, nomor):
        """Membersihkan dan menstandarisasi format nomor telepon ke format internasional (62)."""
        if not nomor:
            return ""
        cleaned = re.sub(r'[^\d+]', '', str(nomor).strip())
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        if cleaned.startswith('0'):
            cleaned = '62' + cleaned[1:]
        elif not cleaned.startswith('62') and len(cleaned) >= 8:
            cleaned = '62' + cleaned
        return cleaned

    def _whatsapp_replace_value(self, text: str, record):
        """Mengganti placeholder {{self.field}} atau {{self.env.user.name}} dengan nilai sebenarnya dari record."""
        if not text or not record:
            return text or ""
        result = text
        pattern = r"\{\{(.*?)\}\}"
        matches = re.findall(pattern, result)

        for match in matches:
            expr = match.strip()
            find = '{{%s}}' % match
            try:
                if expr.startswith('self.env.'):
                    env_path = expr[len('self.env.'):]
                    parts = env_path.split('.')
                    value = record.env
                    for part in parts:
                        value = getattr(value, part, '')
                        if not value:
                            break
                    val_str = str(value) if value else ''
                elif expr.startswith('self.'):
                    field_path = expr[len('self.'):]
                    parts = field_path.split('.')
                    value = record
                    for part in parts:
                        value = getattr(value, part, '')
                        if not value:
                            break
                    val_str = str(value) if value else ''
                else:
                    val_str = ''
            except Exception:
                val_str = ''
            result = result.replace(find, val_str)

        return result

    @api.model
    def _fonnte_send_message(self, config, target, message, attachment_bytes=None, filename=None, delay=None, country_code=None):
        """
        Mengirim pesan teks dan/atau dokumen lampiran melalui endpoint resmi Fonnte: POST /send
        Menggunakan multipart form-data jika ada lampiran, sehingga bekerja langsung pada lingkungan Docker/localhost.
        """
        if not config:
            raise UserError(_("Konfigurasi Fonnte Gateway belum ditentukan."))
        if not config.token:
            raise UserError(_("Token API Fonnte belum diisi pada konfigurasi '%s'.") % config.name)

        base_url = (config.base_url or 'https://api.fonnte.com').rstrip('/')
        url = f"{base_url}/send"
        headers = {
            'Authorization': config.token.strip(),
        }

        # Standarisasi target nomor (dapat berupa string comma-separated)
        targets_list = [self._convert_to_62(n) for n in re.split(r'[,;\n]+', str(target)) if n.strip()]
        if not targets_list:
            raise UserError(_("Nomor tujuan WhatsApp tidak valid."))
        targets_str = ','.join(targets_list)

        payload = {
            'target': targets_str,
            'message': message or '',
            'countryCode': country_code or config.country_code or '62',
        }
        if delay or config.delay:
            payload['delay'] = str(delay if delay is not None else config.delay)

        files = None
        if attachment_bytes:
            safe_filename = filename or 'dokumen.pdf'
            # Jika nama file tidak memiliki ekstensi, deteksi dari header file atau default ke .pdf
            if '.' not in safe_filename:
                if attachment_bytes.startswith(b'%PDF'):
                    safe_filename += '.pdf'
                elif attachment_bytes.startswith(b'\x89PNG'):
                    safe_filename += '.png'
                elif attachment_bytes.startswith(b'\xff\xd8\xff'):
                    safe_filename += '.jpg'
                elif attachment_bytes.startswith(b'PK\x03\x04'):
                    safe_filename += '.xlsx'
                elif b',' in attachment_bytes[:100] or b'|' in attachment_bytes[:100] or b'\t' in attachment_bytes[:100]:
                    safe_filename += '.csv'
                else:
                    safe_filename += '.pdf'

            import mimetypes
            content_type, _ = mimetypes.guess_type(safe_filename)
            content_type = content_type or 'application/octet-stream'

            payload['filename'] = safe_filename
            files = {
                'file': (safe_filename, attachment_bytes, content_type)
            }

        try:
            _logger.info("Mengirim pesan WhatsApp via Fonnte ke %s (dengan file: %s)", targets_str, bool(files))
            if files:
                response = requests.post(url, headers=headers, data=payload, files=files, timeout=45)
            else:
                response = requests.post(url, headers=headers, data=payload, timeout=25)

            try:
                res_data = response.json()
            except Exception:
                res_data = {'status': response.ok, 'raw_response': response.text}

            _logger.info("Respon API Fonnte send message: %s", res_data)
            return res_data
        except requests.exceptions.Timeout:
            raise UserError(_("Koneksi ke server Fonnte timeout. Silakan periksa jaringan internet Anda."))
        except Exception as e:
            _logger.error("Error saat request ke Fonnte API: %s", str(e))
            raise UserError(_("Gagal menghubungi server Fonnte: %s") % str(e))

    @api.model
    def _fonnte_get_qr(self, config):
        """Meminta QR Code untuk pairing device dari Fonnte: POST /qr"""
        if not config or not config.token:
            raise UserError(_("Token Fonnte belum diisi."))
        base_url = (config.base_url or 'https://api.fonnte.com').rstrip('/')
        url = f"{base_url}/qr"
        headers = {'Authorization': config.token.strip()}
        payload = {
            'type': 'qr',
            'whatsapp': config.session_name or '',
        }
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=20)
            return response.json()
        except Exception as e:
            raise UserError(_("Gagal mendapatkan QR Code Fonnte: %s") % str(e))

    @api.model
    def _fonnte_get_device(self, config):
        """Mengambil data status perangkat, kuota, nomor, dan paket dari Fonnte: POST /device"""
        if not config or not config.token:
            raise UserError(_("Token Fonnte belum diisi."))
        base_url = (config.base_url or 'https://api.fonnte.com').rstrip('/')
        url = f"{base_url}/device"
        headers = {'Authorization': config.token.strip()}
        try:
            response = requests.post(url, headers=headers, timeout=20)
            return response.json()
        except Exception as e:
            raise UserError(_("Gagal memeriksa status perangkat Fonnte: %s") % str(e))

    @api.model
    def _fonnte_disconnect(self, config):
        """Memutus sesi koneksi WhatsApp dari Fonnte: POST /disconnect"""
        if not config or not config.token:
            raise UserError(_("Token Fonnte belum diisi."))
        base_url = (config.base_url or 'https://api.fonnte.com').rstrip('/')
        url = f"{base_url}/disconnect"
        headers = {'Authorization': config.token.strip()}
        try:
            response = requests.post(url, headers=headers, timeout=20)
            return response.json()
        except Exception as e:
            raise UserError(_("Gagal memutuskan koneksi Fonnte: %s") % str(e))

    @api.model
    def _fonnte_validate_phone(self, config, target, country_code='62'):
        """Memvalidasi apakah nomor terdaftar di WhatsApp: POST /validate"""
        if not config or not config.token:
            raise UserError(_("Token Fonnte belum diisi."))
        base_url = (config.base_url or 'https://api.fonnte.com').rstrip('/')
        url = f"{base_url}/validate"
        headers = {'Authorization': config.token.strip()}
        payload = {
            'target': self._convert_to_62(target),
            'countryCode': country_code or '62',
        }
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=20)
            return response.json()
        except Exception as e:
            raise UserError(_("Gagal memvalidasi nomor telepon: %s") % str(e))
