from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image

from .classify import check_entity_form_compatibility, classify_entity, route_to_pathway
from .disposition import build_validation_result, determine_disposition
from .extract_llm import extract_fields_via_llm
from .models import CheckResult, CheckSeverity, Disposition, ExtractedFields, ValidationResult
from .output import generate_correction_email, generate_summary_line
from .validate import run_all_checks

app = FastAPI(title="Certificate Validation API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _save_upload(upload: UploadFile, temp_dir: Path) -> Path:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".pdf", ".png"}:
        raise HTTPException(status_code=400, detail="Only PDF and PNG files are supported")

    upload_path = temp_dir / f"upload{suffix}"
    with upload_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return upload_path


def _prepare_document_path(upload_path: Path, temp_dir: Path) -> Path:
    if upload_path.suffix.lower() == ".pdf":
        return upload_path

    image_path = temp_dir / "upload_page.png"
    if image_path != upload_path:
        shutil.copy(upload_path, image_path)

    pdf_path = temp_dir / "upload.pdf"
    with Image.open(image_path) as image:
        image.convert("RGB").save(pdf_path, format="PDF")
    return pdf_path


def _resolve_state(extracted_state: str | None) -> str:
    return (extracted_state or "").strip().upper() or "UNKNOWN"


def _run_validation(fields: ExtractedFields) -> ValidationResult:
    form_type = fields.form_type_detected
    entity_type = classify_entity(fields)
    resolved_state = _resolve_state(fields.purchaser_state)

    compatibility_ok, compatibility_error = check_entity_form_compatibility(resolved_state, entity_type, form_type)
    pathway = route_to_pathway(form_type, entity_type, fields)
    checks = run_all_checks(fields, form_type, entity_type, pathway, resolved_state)

    if not compatibility_ok and compatibility_error:
        checks.insert(
            0,
            CheckResult(
                check_name="classify.entity_form_compatibility",
                passed=False,
                severity=CheckSeverity.HARD_FAIL,
                message=compatibility_error,
                recommendation="Resubmit using entity-appropriate form.",
            ),
        )

    disposition, confidence_score = determine_disposition(checks, fields, form_type, entity_type)
    return build_validation_result(
        fields=fields,
        form_type=form_type,
        entity_type=entity_type,
        pathway=pathway,
        state=resolved_state,
        checks=checks,
        disposition=disposition,
        confidence_score=confidence_score,
    )


def _build_response(extracted_fields: ExtractedFields, result: ValidationResult, error_note: str | None = None) -> dict:
    notes = [flag.message for flag in result.reasonableness_flags]
    if result.human_review_reason:
        notes.append(result.human_review_reason)
    if error_note:
        notes.append(error_note)

    response = {
        "extracted_fields": extracted_fields.model_dump(mode="json"),
        "validation": {
            "disposition": result.disposition.value,
            "hard_fails": [item.message for item in result.hard_fails],
            "soft_fails": [item.message for item in result.soft_flags],
            "notes": notes,
        },
        "summary": generate_summary_line(result),
    }

    if result.disposition == Disposition.NEEDS_CORRECTION:
        response["correction_email"] = generate_correction_email(result)

    return response


@app.post("/validate")
def validate_certificate(file: UploadFile = File(...)) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        upload_path = _save_upload(file, temp_dir)
        document_path = _prepare_document_path(upload_path, temp_dir)

        try:
            extracted_fields = extract_fields_via_llm(str(document_path), fallback_to_regex=False)
            result = _run_validation(extracted_fields)
            return _build_response(extracted_fields, result)
        except Exception as exc:
            error_message = f"Extraction failed: {exc}"
            fallback_fields = ExtractedFields(raw_text=error_message)
            review_result = ValidationResult(
                customer_name="Unknown Customer",
                state="UNKNOWN",
                form_type="Unknown",
                entity_type="Unknown",
                pathway=1,
                seller_protection_standard="Good Faith",
                disposition=Disposition.NEEDS_HUMAN_REVIEW,
                confidence_score=0,
                hard_fails=[],
                soft_flags=[],
                reasonableness_flags=[],
                checks=[],
                human_review_needed=True,
                human_review_reason=error_message,
            )
            return _build_response(fallback_fields, review_result, error_note=error_message)
