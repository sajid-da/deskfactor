import httpx
import pytest

from app.services.ocr.ocr_space import OCRSpaceClient, OCRSpaceError, OCRSpaceTimeout

TEST_KEY = "test-only-key"
SAMPLE_TEXT = "Synthetic handwritten clinical note: patient reports fever."


def response(parsed_text=SAMPLE_TEXT, *, engine_exit=1, page_exit=1, errored=False):
    return {
        "OCRExitCode": engine_exit,
        "IsErroredOnProcessing": errored,
        "ParsedResults": [{"FileParseExitCode": page_exit, "ParsedText": parsed_text}],
    }


def test_uploads_actual_bytes_and_selects_engine_three_for_handwriting():
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json=response())

    client = OCRSpaceClient(TEST_KEY, transport=httpx.MockTransport(handler))
    result = client.recognize(b"real uploaded fixture bytes", "written.png", "image/png", handwriting=True)
    request = seen["request"]
    assert request.headers["apikey"] == TEST_KEY
    assert b"real uploaded fixture bytes" in request.content
    assert b'name="OCREngine"\r\n\r\n3' in request.content
    assert result.text == SAMPLE_TEXT
    assert result.engine_name == "OCR.space Engine 3"
    assert result.status == "success"


def test_printed_documents_use_engine_two():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response()))
    result = OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "print.jpg", "image/jpeg")
    assert result.engine_name == "OCR.space Engine 2"


def test_empty_parsed_text_is_low_confidence_not_success():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response("")))
    result = OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "blank.png", "image/png")
    assert result.text == ""
    assert result.status == "low_confidence"


def test_provider_processing_error_is_reported():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response(None, engine_exit=4, errored=True)))
    with pytest.raises(OCRSpaceError, match="could not process"):
        OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "scan.pdf", "application/pdf")


def test_page_error_with_no_text_is_low_confidence():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response(None, engine_exit=3, page_exit=-10)))
    result = OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "bad.png", "image/png")
    assert result.status == "low_confidence"
    assert result.text == ""


def test_timeout_is_distinguished_from_provider_error():
    def handler(request):
        raise httpx.ReadTimeout("test timeout")

    transport = httpx.MockTransport(handler)
    with pytest.raises(OCRSpaceTimeout, match="timed out"):
        OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "scan.png", "image/png")


@pytest.mark.parametrize("payload", [[], {"OCRExitCode": 1}, {"OCRExitCode": "bad", "ParsedResults": []},
                                      {"OCRExitCode": 1, "ParsedResults": ["not a page"]},
                                      {"OCRExitCode": 1, "ParsedResults": [{"FileParseExitCode": 1, "ParsedText": 12}]}])
def test_invalid_response_shapes_are_rejected(payload):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(OCRSpaceError):
        OCRSpaceClient(TEST_KEY, transport=transport).recognize(b"bytes", "input.png", "image/png")


def test_invalid_json_and_http_status_are_errors():
    invalid_json = httpx.MockTransport(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(OCRSpaceError, match="malformed JSON"):
        OCRSpaceClient(TEST_KEY, transport=invalid_json).recognize(b"bytes", "input.png", "image/png")
    http_failure = httpx.MockTransport(lambda request: httpx.Response(429))
    with pytest.raises(OCRSpaceError, match="HTTP 429"):
        OCRSpaceClient(TEST_KEY, transport=http_failure).recognize(b"bytes", "input.png", "image/png")


def test_missing_key_fails_closed():
    with pytest.raises(OCRSpaceError, match="not configured"):
        OCRSpaceClient("").recognize(b"bytes", "input.png", "image/png")
