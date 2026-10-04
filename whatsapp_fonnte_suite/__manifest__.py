# -*- coding: utf-8 -*-
{
    'name': "WhatsApp Fonnte Suite & Chatter",
    'summary': "Kirim Pesan & Lampiran WhatsApp via Fonnte Gateway langsung dari Chatter Odoo 18",
    'description': """
WhatsApp Fonnte Suite & Chatter Integration for Odoo 18
=======================================================
Modul integrasi resmi Fonnte WhatsApp Gateway pada Odoo 18:
* Tombol WhatsApp langsung di Panel Chatter samping Activities.
* Kirim pesan teks dan lampiran dokumen (PDF/Gambar) langsung ke WhatsApp.
* Wizard interaktif dengan multi-penerima (res.users dan nomor telepon manual).
* Dukungan formatting internasional otomatis (Country Code 62).
* Wizard Scan QR Code & Cek Status Perangkat (Device, Baterai, Kuota, Masa Aktif).
* Fitur Validasi Nomor WhatsApp terdaftar sebelum kirim pesan.
* Template pesan WhatsApp dinamis dengan field record Odoo.
* Pencatatan riwayat pesan otomatis ke timeline Chatter dokumen.
* Link akses instan dokumen Odoo melalui URL redirect /wa/d/<model>/<id>.
* Mendukung pengiriman file aman melalui direct multipart binary upload (bekerja pada localhost dan server publik).
    """,
    'author': "Tyr",
    'website': "https://github.com/evosasori/whatsapp_fonnte_suite",
    'support': "triadisputra123@gmail.com",
    'category': 'Productivity/Discuss',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/fonnte_configuration_views.xml',
        'views/fonnte_template_views.xml',
        'wizards/fonnte_connection_wizard_views.xml',
        'wizards/fonnte_validate_wizard_views.xml',
        'wizards/chatter_whatsapp_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'whatsapp_fonnte_suite/static/src/chatter/chatter.xml',
            'whatsapp_fonnte_suite/static/src/chatter/chatter_patch.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
