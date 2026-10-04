# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class FonnteWhatsappController(http.Controller):

    @http.route('/wa/d/<string:model>/<int:res_id>', type='http', auth='user', website=False)
    def whatsapp_redirect_doc(self, model, res_id, **kwargs):
        """
        Redirect otomatis dari tautan pesan WhatsApp ke form view dokumen terkait di Odoo backend.
        Bila user belum login, Odoo secara otomatis meminta autentikasi terlebih dahulu.
        """
        redirect_url = f"/web#id={res_id}&model={model}&view_type=form"
        return request.redirect(redirect_url)

    @http.route('/whatsapp/fonnte/webhook', type='json', auth='none', methods=['POST'], csrf=False)
    def fonnte_webhook_receiver(self, **kwargs):
        """
        Webhook receiver untuk menangani pesan masuk (incoming message) dan delivery report (status pengiriman) dari Fonnte.
        """
        try:
            data = request.get_json_data() or kwargs
            _logger.info("Fonnte Webhook Received: %s", json.dumps(data))
            # Endpoint disiapkan untuk kustomisasi respon interaktif
            return {'status': True, 'message': 'Webhook received successfully'}
        except Exception as e:
            _logger.error("Error processing Fonnte webhook: %s", str(e))
            return {'status': False, 'error': str(e)}
