from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.ui import gradio_app


class _FakePipeline:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, *, image_path, description, user_inputs):
        self.calls.append(
            {
                "image_path": image_path,
                "description": description,
                "user_inputs": user_inputs,
            }
        )
        return self.result


def _fake_result(tmp_path: Path, *, success: bool = True):
    package = tmp_path / "output" / "demo-passport"
    package.mkdir(parents=True)

    passport_json_path = package / "passport.json"
    passport_html_path = package / "passport.html"
    gap_report_path = package / "gap_report.html"
    qr_path = package / "qr.png"

    passport_json_path.write_text('{"ok": true}', encoding="utf-8")
    passport_html_path.write_text("<html><body>Passport</body></html>", encoding="utf-8")
    gap_report_path.write_text("<html><body>Gap</body></html>", encoding="utf-8")
    qr_path.write_bytes(b"qr")

    return SimpleNamespace(
        success=success,
        passport_id="demo-passport",
        reconciled_domain_data={"espr_core": {"product_group": "batteries"}},
        passport_json={"ok": True},
        readiness_score=88,
        readiness_verdict="ready_with_gaps",
        is_publishable=False,
        package_url="https://example.test/passports/demo-passport/passport.html",
        qr_url="https://example.test/passports/demo-passport/qr.png",
        warnings=[],
        errors=[] if success else ["failed"],
        artifact_paths={
            "passport.json": passport_json_path,
            "passport.html": passport_html_path,
            "gap_report.html": gap_report_path,
            "qr.png": qr_path,
        },
        agent_outputs={"vision": {"success": True, "is_mock": True}},
    )


def test_minimum_input_validation_requires_photo():
    errors = gradio_app.validate_minimum_inputs(
        image_path=None,
        product_group="batteries",
        brand_name="Demo Brand",
        description="Battery pack",
    )

    assert errors == ["Upload a product photo before generating a passport."]


def test_initial_action_state_is_disabled():
    assert gradio_app.build_initial_action_state() == {
        "open_passport": False,
        "open_gap_report": False,
        "download_json": False,
        "download_zip": False,
        "open_public_url": False,
        "push_to_s3": False,
        "generate_qr": False,
    }


def test_action_state_enabled_after_success(tmp_path):
    result = _fake_result(tmp_path)

    action_state = gradio_app.build_action_state(result)

    assert action_state["open_passport"] is True
    assert action_state["open_gap_report"] is True
    assert action_state["download_json"] is True
    assert action_state["download_zip"] is True
    assert action_state["open_public_url"] is True
    assert action_state["generate_qr"] is False


def test_create_zip_package_includes_artifacts(tmp_path):
    result = _fake_result(tmp_path)

    zip_path = gradio_app.create_zip_package(
        "demo-passport",
        artifact_paths=result.artifact_paths,
        output_dir=tmp_path / "output",
    )

    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "gap_report.html",
            "passport.html",
            "passport.json",
            "qr.png",
        ]


def test_run_generation_calls_pipeline_once_and_maps_result(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"image")
    result = _fake_result(tmp_path)
    fake_pipeline = _FakePipeline(result)

    def pipeline_factory(**kwargs):
        assert kwargs["runtime_mode"] == "demo_mock"
        assert kwargs["storage_mode"] == "local"
        return fake_pipeline, "local"

    view = gradio_app.run_generation(
        image_path=image_path,
        description="Battery pack",
        product_group="batteries",
        brand_name="Demo Brand",
        runtime_mode="demo_mock",
        storage_mode="local",
        output_dir=tmp_path / "output",
        pipeline_factory=pipeline_factory,
    )

    assert view.success is True
    assert len(fake_pipeline.calls) == 1
    assert fake_pipeline.calls[0]["user_inputs"]["brand_name"] == "Demo Brand"
    assert fake_pipeline.calls[0]["user_inputs"]["product_group"] == "batteries"
    assert view.passport_json == {"ok": True}
    assert view.qr_path and view.qr_path.endswith("qr.png")
    assert view.zip_path and Path(view.zip_path).exists()
    assert "Demo mode" in "\n".join(view.state["warnings"])


def test_run_generation_returns_error_view_without_pipeline_call(tmp_path):
    called = False

    def pipeline_factory(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("Pipeline should not be built when validation fails")

    view = gradio_app.run_generation(
        image_path=None,
        description="Battery pack",
        product_group="batteries",
        brand_name="Demo Brand",
        runtime_mode="demo_mock",
        storage_mode="local",
        output_dir=tmp_path / "output",
        pipeline_factory=pipeline_factory,
    )

    assert called is False
    assert view.success is False
    assert "Upload a product photo" in view.run_summary_markdown


def test_live_gemma_failed_vision_is_marked_as_error(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"image")
    result = _fake_result(tmp_path)
    result.agent_outputs = {"vision": {"success": False, "error": "Ollama failed"}}
    fake_pipeline = _FakePipeline(result)

    def pipeline_factory(**kwargs):
        return fake_pipeline, "local"

    view = gradio_app.run_generation(
        image_path=image_path,
        description="Battery pack",
        product_group="batteries",
        brand_name="Demo Brand",
        runtime_mode="live_gemma",
        storage_mode="local",
        output_dir=tmp_path / "output",
        pipeline_factory=pipeline_factory,
    )

    assert view.success is False
    assert any("Gemma vision analysis failed" in error for error in view.state["errors"])


def test_build_interface_returns_gradio_blocks():
    interface = gradio_app.build_interface()

    assert interface is not None


def test_actions_use_package_url_not_public_url_wording():
    html = gradio_app._build_actions_html(None)

    assert "Open Package URL" in html
    assert "Open Public URL" not in html
    assert "cloud" not in html.lower()


def test_run_summary_separates_readiness_from_storage(tmp_path):
    result = _fake_result(tmp_path)

    summary = gradio_app._format_run_summary(
        result,
        runtime_mode="demo_mock",
        storage_mode="s3",
        zip_path=None,
    )

    assert "#### Readiness" in summary
    assert "#### Storage" in summary
    assert "Package URL" in summary
    assert "cloud" not in summary.lower()


def test_chat_messages_use_gradio_messages_format(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"image")
    fake_pipeline = _FakePipeline(_fake_result(tmp_path))

    def pipeline_factory(**kwargs):
        return fake_pipeline, "local"

    view = gradio_app.run_generation(
        image_path=image_path,
        description="Battery pack",
        product_group="batteries",
        brand_name="Demo Brand",
        runtime_mode="demo_mock",
        storage_mode="local",
        output_dir=tmp_path / "output",
        pipeline_factory=pipeline_factory,
    )

    assert view.messages
    assert isinstance(view.messages[0], dict)
    assert set(view.messages[0]) == {"role", "content"}
    assert view.messages[0]["role"] == "assistant"
