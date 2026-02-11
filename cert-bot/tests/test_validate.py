from datetime import date

from src.models import CheckResult, CheckSeverity, ExemptionCategory, ExtractedFields, FormType
from src.validate import (
    check_cert_age,
    check_compound_failure,
    check_expiration,
    check_future_date,
    check_mtc_resale_only,
    check_purchaser_name_is_entity,
    check_sst_member,
)


def test_compound_failure():
    """3+ hard fails should trigger compound failure."""
    results = [
        CheckResult(check_name="c1", passed=False, severity=CheckSeverity.HARD_FAIL, message="fail1"),
        CheckResult(check_name="c2", passed=False, severity=CheckSeverity.HARD_FAIL, message="fail2"),
        CheckResult(check_name="c3", passed=False, severity=CheckSeverity.HARD_FAIL, message="fail3"),
    ]
    compound = check_compound_failure(results)
    assert compound is not None
    assert compound.passed is False
    assert compound.severity == CheckSeverity.HARD_FAIL


def test_compound_failure_below_threshold():
    """2 hard fails should NOT trigger compound failure."""
    results = [
        CheckResult(check_name="c1", passed=False, severity=CheckSeverity.HARD_FAIL, message="fail1"),
        CheckResult(check_name="c2", passed=False, severity=CheckSeverity.HARD_FAIL, message="fail2"),
    ]
    compound = check_compound_failure(results)
    assert compound is None


def test_personal_name_detection():
    """'Donna Miller' should be flagged as personal name."""
    fields = ExtractedFields(purchaser_name="Donna Miller", raw_text="")
    result = check_purchaser_name_is_entity(fields)
    assert result.passed is False


def test_entity_name_passes():
    """'Waller Harris ESD 200' should pass entity name check."""
    fields = ExtractedFields(purchaser_name="Waller Harris ESD 200", raw_text="")
    result = check_purchaser_name_is_entity(fields)
    assert result.passed is True


def test_expiration_never_expires():
    """TX certs never expire."""
    fields = ExtractedFields(cert_date=date(2020, 1, 1), raw_text="")
    result = check_expiration(fields, "TX", FormType.TX_01_339)
    assert result.passed is True


def test_expiration_al_annual():
    """AL certs expire annually. A cert from 2 years ago should fail."""
    fields = ExtractedFields(cert_date=date(2024, 1, 1), raw_text="")
    result = check_expiration(fields, "AL", FormType.AL_STE_1)
    assert result.passed is False
    assert result.severity == CheckSeverity.HARD_FAIL


def test_mtc_resale_only_tn():
    """MTC form with non-resale exemption in TN should fail."""
    fields = ExtractedFields(
        purchaser_name="City of Nashville",
        exemption_reason="Government Entity",
        exemption_category=ExemptionCategory.GOVERNMENT,
        raw_text="",
    )
    result = check_mtc_resale_only(fields, FormType.MTC_UNIFORM, "TN")
    assert result is not None
    assert result.passed is False


def test_mtc_resale_ok_tn():
    """MTC form with resale exemption in TN should pass."""
    fields = ExtractedFields(
        purchaser_name="IT Solutions LLC",
        exemption_reason="Resale",
        exemption_category=ExemptionCategory.RESALE,
        raw_text="",
    )
    result = check_mtc_resale_only(fields, FormType.MTC_UNIFORM, "TN")
    assert result is not None
    assert result.passed is True


def test_sst_non_member_fails():
    """SST form used in non-SST state (TX) should fail."""
    result = check_sst_member(FormType.SST_F0003, "TX")
    assert result is not None
    assert result.passed is False


def test_sst_member_passes():
    """SST form used in SST state (OH) should pass."""
    result = check_sst_member(FormType.SST_F0003, "OH")
    assert result is not None
    assert result.passed is True


def test_future_date_fails():
    """Cert with future date should fail."""
    fields = ExtractedFields(cert_date=date(2027, 6, 1), raw_text="")
    result = check_future_date(fields)
    assert result is not None
    assert result.passed is False


def test_cert_age_flag_for_old_cert():
    """A 5+ year old cert should soft flag."""
    fields = ExtractedFields(cert_date=date(2018, 1, 1), raw_text="")
    result = check_cert_age(fields)
    assert result is not None
    assert result.passed is False
    assert result.severity == CheckSeverity.SOFT_FLAG
