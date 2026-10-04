/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Chatter.prototype, {
    async onClickWhatsapp() {
        this.closeSearch?.();
        const openWhatsappWizard = async (thread) => {
            await this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Kirim Pesan WhatsApp"),
                res_model: "chatter.whatsapp.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {
                    active_model: thread.model,
                    active_id: thread.id,
                    active_ids: [thread.id],
                    default_res_model: thread.model,
                    default_res_id: thread.id,
                },
            }, {
                onClose: () => {
                    this.load(thread, ["messages"]);
                    this.reloadParentView?.();
                },
            });
        };

        if (this.state.thread?.id) {
            await openWhatsappWizard(this.state.thread);
        } else {
            this.onThreadCreated = openWhatsappWizard;
            await this.props.saveRecord?.();
        }
    },
});
