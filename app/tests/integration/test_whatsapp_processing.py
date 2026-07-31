"""Integration tests for the tenant-side WhatsApp processing: an inbound
delivery becomes a conversation + message, links to a patient by phone, is
idempotent on retry, and outbound status updates apply.

Identifiers are randomised per run because the processor commits (rollback
can't undo it), so tests must not assume an empty shared database.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models.all_models import WhatsAppConversation, WhatsAppMessage
from app.services.whatsapp_service import _TenantMessageProcessor, parse_change_value


def _rand_waid() -> str:
    return "234" + str(uuid.uuid4().int)[:10]


def _rand_wamid() -> str:
    return "wamid." + uuid.uuid4().hex


def _config():
    return SimpleNamespace(
        phone_number_id="106540352242922",
        display_phone_number="15550783881",
        notify_role_codes=None,
    )


def _inbound_value(wa_id, wamid, body="Hello clinic", name="Sheena Nelson"):
    return {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550783881",
                     "phone_number_id": "106540352242922"},
        "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
        "messages": [{
            "from": wa_id, "id": wamid, "timestamp": "1749416383",
            "type": "text", "text": {"body": body},
        }],
    }


class TestInboundProcessing:
    def test_creates_conversation_and_message(self, db_session):
        wa_id, wamid = _rand_waid(), _rand_wamid()
        parsed = parse_change_value(_inbound_value(wa_id, wamid))
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()

        msg = (db_session.query(WhatsAppMessage)
               .filter(WhatsAppMessage.wa_message_id == wamid).first())
        assert msg is not None
        assert msg.direction == "INBOUND"
        assert msg.body == "Hello clinic"
        assert msg.message_type == "TEXT"

        conv = db_session.get(WhatsAppConversation, msg.conversation_id)
        assert conv.wa_id == wa_id
        assert conv.contact_name == "Sheena Nelson"
        assert conv.unread_count >= 1
        assert conv.last_inbound_at is not None

    def test_idempotent_on_retry(self, db_session):
        wa_id, wamid = _rand_waid(), _rand_wamid()
        parsed = parse_change_value(_inbound_value(wa_id, wamid))
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()
        # Same delivery again (Meta retry) must not create a second row.
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()
        count = (db_session.query(WhatsAppMessage)
                 .filter(WhatsAppMessage.wa_message_id == wamid).count())
        assert count == 1

    def test_links_to_patient_by_phone(self, db_session):
        from app.models.all_models import Patient
        wa_id, wamid = _rand_waid(), _rand_wamid()
        patient = Patient(
            global_patient_id="GPID-" + uuid.uuid4().hex[:12],
            hospital_number="HN-" + uuid.uuid4().hex[:8].upper(),
            first_name="Test", last_name="Patient", phone_number=wa_id,
        )
        db_session.add(patient)
        db_session.commit()
        parsed = parse_change_value(_inbound_value(wa_id, wamid))
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()

        msg = (db_session.query(WhatsAppMessage)
               .filter(WhatsAppMessage.wa_message_id == wamid).first())
        conv = db_session.get(WhatsAppConversation, msg.conversation_id)
        assert conv.patient_id == patient.id
        assert msg.patient_id == patient.id


class TestOutboundStatusUpdates:
    def _seed_outbound(self, db_session, status):
        conv = WhatsAppConversation(phone_number_id="106540352242922",
                                    wa_id=_rand_waid(), status="OPEN", unread_count=0)
        db_session.add(conv)
        db_session.flush()
        wamid = _rand_wamid()
        out = WhatsAppMessage(conversation_id=conv.id, wa_message_id=wamid,
                              direction="OUTBOUND", message_type="TEXT",
                              body="hi", status=status)
        db_session.add(out)
        db_session.commit()
        return out, wamid

    def test_status_update_applies(self, db_session):
        out, wamid = self._seed_outbound(db_session, "SENT")
        parsed = parse_change_value({
            "metadata": {"phone_number_id": "106540352242922"},
            "statuses": [{"id": wamid, "status": "delivered", "timestamp": "1749416400"}],
        })
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()
        db_session.refresh(out)
        assert out.status == "DELIVERED"
        assert out.status_updated_at is not None

    def test_out_of_order_status_does_not_regress(self, db_session):
        out, wamid = self._seed_outbound(db_session, "READ")
        # A late 'sent' arriving after 'read' must not move it backwards.
        parsed = parse_change_value({
            "metadata": {"phone_number_id": "106540352242922"},
            "statuses": [{"id": wamid, "status": "sent", "timestamp": "1"}],
        })
        _TenantMessageProcessor(db_session, _config()).apply(parsed)
        db_session.commit()
        db_session.refresh(out)
        assert out.status == "READ"
