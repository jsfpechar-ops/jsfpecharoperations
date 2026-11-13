"""App/app/migrations/ is frozen at 0045 (plan sqlite-retirement S1, brief 1470).

PostgreSQL's schema authority is the goose files in App/migrations_pg/. The
SQLite files below are still translated and run by Python's apply, so a new
or edited file there would change production behind goose's back. FROZEN is
the name and sha256 of every file in the folder (CRLF read as LF, so a
Windows checkout does not fail); the check needs no git history.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app import db

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"
LAST_FROZEN = 45

WHAT_TO_DO = (
    "App/app/migrations/ is frozen at 0045 (docs/plans/sqlite-retirement.md, step S1). "
    "Do not add, edit, rename or delete a file there, and do not edit FROZEN or "
    "LAST_FROZEN in this test to make it pass. Undo the change in App/app/migrations/ "
    "and write the schema change as a new goose file in App/migrations_pg/ "
    "(number = highest there + 1)."
)

FROZEN = {
    ".gitkeep": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "0002_apartment_slug.sql": "3bc741f7a472ee632767e667d38f3e9d023dfdd6cad905f34340a8c41ce10b87",
    "0003_signup.sql": "549e551adc06886e7ac5d8018aca217e83de2cd931eadc3c14c2a3dd09d63d21",
    "0004_meta_capi.sql": "c359a2c793b8df828eb35a19592bc87af509e1fc9382948b7ea54e7ea895660c",
    "0005_email_login.sql": "739befdd7aa5f6b08f4ce6b164a50474ca938686f7c6bc95564d44c273960348",
    "0006_passkeys.sql": "9742acc7ba34c15e5714f41629f5589475fb6fd60ad5cbb40115e953350b94d7",
    "0007_door_codes.sql": "e83c29fa4420136b7ce90c44acac12ae83607ff40a81c79fca84e9b61d619358",
    "0008_posthog_stage.sql": "75145a6fcfd8979e7c7aa259515c0de6f5a8ed1230afc55599b98e5659d01d39",
    "0009_stay_fee_send.sql": "00d4caf8006329eed9300dbe615a903ea9d39f942819c1ba2c92bc2ab7975eb9",
    "0010_cleaning.sql": "71543648a0b6a3f819fa1e34fdb4b1142f9b3676317c307065b7e4c2ab96fd41",
    "0011_stay_fee_emails.sql": "0877b0302dc6e197c535b05c81e55b8770ef5d4640c312572f06eac90465b894",
    "0012_web_push.sql": "0e2bc6d9ef0be0f2db594f8abf4080f2a4a8252cc92d28ca57c013c80b515671",
    "0013_guest_guide.sql": "e425cca8a9b5716d01c53bfc56063c472f6ba32678df9040080767a61a480e71",
    "0014_guide_token.sql": "216492fdbbc0ac9f99d31e9b6dabfb24ac851f7a6029546ea27956fc1de5cd82",
    "0015_ai_usage.sql": "de24a6e121f33f2ac992de3b402988a4a2ce37a4c694e15c7c38b2a4500bb6b0",
    "0016_guide_import.sql": "5727f199fbe9b2f79d31aa6e371f765d4f7cdb08056b2087071936315fb588a2",
    "0017_guest_chat.sql": "901472938861cb2a4dcc22c6aba5c3e461ce3a2c2f91be8a2684d0343aee35d2",
    "0018_guide_translation.sql": "7a6eb09a069d9c4b19288321528e6f379abb167baf301aa41622f175f3940ced",
    "0019_guide_fact.sql": "20cf20e0adb8f366c8cae8a4397ae1f512f33077a96a878a42c7bd0f636a001b",
    "0020_havel_gap.sql": "5f0a9868ebd9b3bd626771c2bc0a9def0883d4ded2e82228dc40019983c23d7f",
    "0021_leon_opt_in.sql": "9fa1c7e8317e18437054e51b758933cb06e70cbe4ee7cdd2796cc7859009f0a2",
    "0022_leon_terms.sql": "3f2b63cd5384a460c643699f5c0f07b3efabb7400ff4942894e089237119e714",
    "0023_billing.sql": "11612f861780b8333452468f5c3c6b9cf1c89dfed46b19f70bcd97a2021ffe92",
    "0024_platform_invoice_pdf.sql": "8cc52e18ae150b76ed466f1949300b7e974b1cdefde22a663d024649feb551b1",
    "0025_signup_selection.sql": "f1d182f4e73096c94b6db45fdc9820a6b03073bec2728d0784787b5af88b25f3",
    "0026_payment_requests.sql": "afa28d25af84bac4b81dda3b83f408564eb996359e73139246dd903a1207c39f",
    "0027_stripe_webhook_events.sql": "f314e9ff2c29c1fb7f6922bb5ded092063a7c9e74e6752c1ebb3c8dc92e37dbd",
    "0028_property_slug.sql": "0cb47640abe6d34762e76a74e55ac2ab3ca64518ace8dcf0e5ce93140e52c586",
    "0029_property_page.sql": "fcd88e9c87cff0009c598210c4b9389db55c563d168a1d69380a3a8a6d470b82",
    "0030_booking_hold.sql": "07fc4c9f14f1cfbdb1a3920733ed03548a5f8f450f05b199d63b490f69f1c5fa",
    "0031_billing_discount_snapshot.sql": "371585f005ec9d30efdad1f6a3645a305aa40d4a197daa5ccce848708a9e3b58",
    "0032_legal_entity_business_type.sql": "65a2a2e8db76e8190a778b7db9e9b1fa7a1661f93493fc70e21aaf8750e6209e",
    "0033_admin_queue_index.sql": "29a38911dc10974bf878d7bbf1f41dde1ba7bf60ce99495df16688596a92d22f",
    "0034_site_booking.sql": "0ec761ad44583c1952ca030d8e258dfe2264283053fef02397c261b2a5d90941",
    "0035_apartment_ocr_scan.sql": "d2c5bd1b7ec41556fa94dbf39dd60f6244aa2f1024cace8c6f8606f10c990728",
    "0036_stay_fee_guest_pay.sql": "0667bf22407494c1441a2249dc05601d7e04d36a901d98f8a9d76542ff1835ad",
    "0037_stay_fee_guest_default_rail.sql": "181c5fd2ea7189351a7f58f5842fca9e944ecce42091418831a5b4b9ed31449f",
    "0038_property_page_house_rules.sql": "211134047dbaeca30ed94b38834b8a30e08d76170e2e4818e0c01948671865a6",
    "0039_site_booking_direct.sql": "ed9a5e1b08b406081ec4f4300ff2044b567779af6c2fc5abfca9af998895b541",
    "0040_stay_fee_rate_history.sql": "342c9472905594a1c71ab4cd5c49e5df26905236bc10220f8651016d3147b32f",
    "0041_claim_fee_mailed.sql": "185b1020dfe82ec9221d4bc669492d617fb09058efb7879ab23bc5477f53d009",
    "0042_guest_form_draft.sql": "628813768b4aca8d033190e0b8722fa233d37b01fbfa922f1bc25cba767ebba6",
    "0043_guest_signed_for.sql": "58119067075f16cac613d2293ed59f2e59a5f86f31aded1998a615c3ba0c4e07",
    "0044_lead_reduced_guests.sql": "3172ff4f0f8aef1d9c592f6813d9089bce08ef6715f4dacf57e994c924ef63a3",
    "0045_guest_details_mail.sql": "bdfb37ac36990700ba9548a8cad4a49bf616131e1a9e4c942e332a6d669f665e",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _found() -> dict:
    return {path.name: path for path in sorted(MIGRATIONS.iterdir())}


def test_no_file_added_or_removed():
    found = set(_found())
    added = sorted(found - set(FROZEN))
    removed = sorted(set(FROZEN) - found)
    assert not added and not removed, f"added: {added}, removed: {removed}. {WHAT_TO_DO}"


def test_no_file_edited():
    found = _found()
    not_files = sorted(name for name, path in found.items() if not path.is_file())
    edited = sorted(
        name for name, path in found.items()
        if path.is_file() and name in FROZEN and _sha256(path) != FROZEN[name]
    )
    assert not not_files and not edited, f"edited: {edited}, not a file: {not_files}. {WHAT_TO_DO}"


def test_the_runner_reads_exactly_the_frozen_files():
    assert db.MIGRATIONS_DIR.resolve() == MIGRATIONS.resolve(), WHAT_TO_DO
    versions = [version for version, _name, _path in db.migration_files()]
    assert versions == list(range(2, LAST_FROZEN + 1)), WHAT_TO_DO


def test_the_manifest_stops_at_0045():
    numbers = sorted(int(name[:4]) for name in FROZEN if name[:4].isdigit())
    assert numbers == list(range(2, LAST_FROZEN + 1)), WHAT_TO_DO
    assert LAST_FROZEN == 45, WHAT_TO_DO
    assert len(FROZEN) == 45, WHAT_TO_DO
