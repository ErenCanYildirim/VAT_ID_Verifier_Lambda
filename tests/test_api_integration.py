import requests
import json
import time
import os
from dotenv import load_dotenv
import pytest
from typing import Dict, Any

load_dotenv()


class VATCheckerAPITest:
    def __init__(self):
        self.api_url_test = os.getenv("API_GATEWAY_URL_TEST")
        self.api_url_prod = os.getenv("API_GATEWAY_URL_PROD")
        self.api_key = os.getenv("API_KEY_VALUE")
        self.region = os.getenv("AWS_REGION")

        required_vars = ["API_GATEWAY_URL_TEST", "API_KEY_VALUE"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

    def make_api_request(
        self, url: str, payload: Dict[str, Any], timeout: int = 30
    ) -> requests.Response:
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout
            )
            return response
        except requests.RequestException as e:
            pytest.fail(f"API request failed: {e}")

    def test_api_authentication(self):
        response = self.make_api_request(
            self.api_url_test, {"vatNumber": "NL123456789B01"}
        )

        assert response.status_code != 401, "Valid API key should not return 401"
        assert response.status_code != 403, "Valid API key should not return 403"

        headers = {"Content-Type": "application/json"}
        response = requests.post(
            self.api_url_test, json={"vatNumber": "NL123456789B01"}, headers=headers
        )
        assert response.status_code in [
            401,
            403,
        ], "Missing API key should return 401 or 403"

    def test_valid_vat_numbers(self):
        valid_vat_numbers = [
            "NL123456789B01",  # Netherlands
            "DE123456789",  # Germany
            "FR12345678901",  # France
            "BE0123456789",  # Belgium
            "AT123456789",  # Austria
        ]

        for vat_number in valid_vat_numbers:
            response = self.make_api_request(
                self.api_url_test, {"vatNumber": vat_number}
            )

            assert response.status_code in [
                200,
                502,
            ], f"VAT {vat_number} should return 200 or 502, got {response.status_code}"

            data = response.json()
            assert (
                "success" in data or "error" in data
            ), "Response should contain success or error"

            if response.status_code == 200 and "success" in data:
                assert (
                    "vatNumber" in data
                ), "Successful response should contain vatNumber"
                assert "data" in data, "Successful response should contain data"

    def test_invalid_vat_numbers(self):
        invalid_vat_numbers = [
            "",  # Empty
            "12",  # Too short
        ]

        for vat_number in invalid_vat_numbers:
            response = self.make_api_request(
                self.api_url_test, {"vatNumber": vat_number}
            )

            assert (
                response.status_code == 400
            ), f"Invalid VAT {vat_number} should return 400"

            data = response.json()
            assert "error" in data, "Error response should contain error field"

    def test_missing_parameters(self):
        response = self.make_api_request(self.api_url_test, {})
        assert response.status_code == 400, "Empty payload should return 400"

        data = response.json()
        assert "error" in data, "Error response should contain error field"
        assert "vatNumber" in data["message"], "Error should mention missing vatNumber"

    def test_soap_method(self):
        response = self.make_api_request(
            self.api_url_test, {"vatNumber": "NL123456789B01", "method": "soap"}
        )
        assert response.status_code in [
            200,
            502,
        ], "SOAP method should return 200 or 502"

    def test_rest_method(self):
        response = self.make_api_request(
            self.api_url_test, {"vatNumber": "NL123456789B01", "method": "rest"}
        )
        assert response.status_code in [
            200,
            502,
        ], "REST method should return 200 or 502"

    def test_production_endpoint(self):
        if not self.api_url_prod:
            pytest.skip("Production URL not available")

        response = self.make_api_request(
            self.api_url_prod, {"vatNumber": "NL123456789B01"}
        )

        assert response.status_code in [
            200,
            502,
        ], "Production endpoint should be accessible"

    def test_response_format(self):
        response = self.make_api_request(
            self.api_url_test, {"vatNumber": "NL123456789B01"}
        )

        assert (
            response.headers.get("content-type") == "application/json"
        ), "Response should be JSON"

        try:
            data = response.json()
        except json.JSONDecodeError:
            pytest.fail("Response should be valid JSON")

    def test_performance(self):
        start_time = time.time()

        response = self.make_api_request(
            self.api_url_test, {"vatNumber": "NL123456789B01"}
        )

        response_time = time.time() - start_time

        assert (
            response_time < 30
        ), f"API response took {response_time:.2f}s, should be < 30s"

        if response_time > 10:
            print(
                f"Warning: API response took {response_time:.2f}s, consider optimization"
            )


def run_integration_tests():
    print("Running integration tests...")

    test_suite = VATCheckerAPITest()

    tests = [
        test_suite.test_api_authentication,
        test_suite.test_missing_parameters,
        test_suite.test_invalid_vat_numbers,
        test_suite.test_valid_vat_numbers,
        test_suite.test_soap_method,
        test_suite.test_rest_method,
        test_suite.test_response_format,
        test_suite.test_performance,
        test_suite.test_production_endpoint,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"Running {test.__name__}...")
            test()
            print(f"{test.__name__} PASSED")
            passed += 1
        except Exception as e:
            print(f"{test.__name__} FAILED: {e}")
            failed += 1
        print()

    print("-" * 50)
    print(f"Integration Tests Complete: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    if not os.getenv("API_GATEWAY_URL_TEST"):
        print("Error: Environment variables not set!")
        print("Run extract_terraform_outputs.py first from the terraform directory")
        exit(1)

    success = run_integration_tests()
    exit(0 if success else 1)
