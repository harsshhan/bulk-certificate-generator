from pathlib import Path

from app.generators.certificate_generator import generate_certificate


def test_generate_certificate(tmp_path):
    output_path = tmp_path / "certificate.pdf"

    generate_certificate(
        recipient_name="Alice Johnson",
        event_name="Python Workshop",
        event_date="2026-10-07",
        output_path=str(output_path),
    )

    assert output_path.exists()
    assert output_path.is_file()
    assert output_path.stat().st_size > 0

def test_generate_certificate_invalid_path():
    invalid_path = "/this/path/does/not/exist/certificate.pdf"

    try:
        generate_certificate(
            recipient_name="Alice Johnson",
            event_name="Python Workshop",
            event_date="2026-10-07",
            output_path=invalid_path,
        )
    except Exception as exc:
        assert exc is not None
    else:
        raise AssertionError("Expected certificate generation to fail")