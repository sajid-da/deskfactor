from dataclasses import dataclass

import httpx

OCR_SPACE_ENDPOINT = "https://api.ocr.space/parse/image"


class OCRSpaceError(RuntimeError):
    """The OCR provider rejected the request or returned an invalid response."""


class OCRSpaceTimeout(OCRSpaceError):
    """The OCR provider did not respond before the configured timeout."""


class OCRSpaceConfigurationError(OCRSpaceError):
    """The OCR provider client is missing its server-side credential."""


@dataclass(frozen=True)
class OCRSpacePage:
    text: str
    exit_code: int


@dataclass(frozen=True)
class OCRSpaceResult:
    text: str
    status: str
    engine_name: str
    pages: list[OCRSpacePage]


def _integer(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OCRSpaceError(f"OCR.space returned an invalid {field}.") from exc


class OCRSpaceClient:
    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 90.0, connect_timeout: float = 10.0):
        self.api_key = api_key.strip()
        self.transport = transport
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    def recognize(self, data: bytes, filename: str, content_type: str, *, handwriting: bool = False) -> OCRSpaceResult:
        if not self.api_key:
            raise OCRSpaceConfigurationError("OCR.space is not configured. Set OCR_SPACE_API_KEY in backend/.env.")
        engine = 3 if handwriting else 2
        params = {
            "language": "auto",
            "isOverlayRequired": "false",
            "detectOrientation": "true",
            "scale": "true",
            "OCREngine": str(engine),
        }
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                response = client.post(
                    OCR_SPACE_ENDPOINT,
                    headers={"apikey": self.api_key},
                    data=params,
                    files={"file": (filename, data, content_type or "application/octet-stream")},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise OCRSpaceTimeout("OCR.space timed out while processing this document. Please retry.") from exc
        except httpx.HTTPStatusError as exc:
            raise OCRSpaceError(f"OCR.space returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise OCRSpaceError("Could not connect to OCR.space. Check the backend network and retry.") from exc
        except ValueError as exc:
            raise OCRSpaceError("OCR.space returned malformed JSON.") from exc

        if not isinstance(payload, dict):
            raise OCRSpaceError("OCR.space returned an invalid response object.")
        processing_error = payload.get("IsErroredOnProcessing")
        if not isinstance(processing_error, bool):
            raise OCRSpaceError("OCR.space returned an invalid processing status.")
        if processing_error:
            raise OCRSpaceError("OCR.space could not process this document.")
        exit_code = _integer(payload.get("OCRExitCode"), "OCRExitCode")
        if exit_code not in {1, 2, 3}:
            raise OCRSpaceError("OCR.space reported a processing failure.")
        parsed_results = payload.get("ParsedResults")
        if parsed_results is None and exit_code == 3:
            parsed_results = []
        if not isinstance(parsed_results, list):
            raise OCRSpaceError("OCR.space returned malformed ParsedResults.")

        pages: list[OCRSpacePage] = []
        for result in parsed_results:
            if not isinstance(result, dict):
                raise OCRSpaceError("OCR.space returned a malformed page result.")
            page_code = _integer(result.get("FileParseExitCode"), "FileParseExitCode")
            parsed_text = result.get("ParsedText")
            if parsed_text is None and page_code != 1:
                parsed_text = ""
            if not isinstance(parsed_text, str):
                raise OCRSpaceError("OCR.space returned invalid ParsedText.")
            pages.append(OCRSpacePage(parsed_text, page_code))

        text = "\n\n".join(page.text for page in pages if page.text)
        successful_pages = sum(page.exit_code == 1 for page in pages)
        alphanumeric = sum(character.isalnum() for character in text)
        if alphanumeric < 8 or successful_pages == 0:
            status = "low_confidence"
        elif exit_code == 2 or successful_pages < len(pages) or alphanumeric < 30:
            status = "partial"
        else:
            status = "success"
        return OCRSpaceResult(text, status, f"OCR.space Engine {engine}", pages)
